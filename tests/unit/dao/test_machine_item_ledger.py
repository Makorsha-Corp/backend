"""Unit tests for app/dao/machine_item_ledger.py.

Implements tests/unit/dao/machine_item_ledger.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None); the commit spy of the "rolled back"
cards wraps the real `db.commit`.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001, FURB157  (Conventions prescribe `with pytest.raises(...)` around
# `with db.begin_nested()`, naive datetimes for the bounds and values, and the Decimal strings as carded)
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from psycopg2.errors import (
    ForeignKeyViolation,
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
    NotNullViolation,
    NumericValueOutOfRange,
    RestrictViolation,
    StringDataRightTruncation,
)
from pydantic import ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import ArgumentError, DataError, IntegrityError

from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_item_ledger import MachineItemLedger
from app.schemas.machine_item_ledger import (
    MachineItemLedgerCreate,
    MachineItemLedgerResponse,
    MachineItemLedgerUpdate,
)
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton machine_item_ledger_dao" (a module-level name, not a fixture)
dao = machine_item_ledger_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999

# Convention "T1 ... T5" (all naive; January, so New York is UTC-5)
T1 = datetime(2026, 1, 1, 9, 0, 0)
T2 = datetime(2026, 1, 1, 10, 0, 0)
T3 = datetime(2026, 1, 1, 11, 0, 0)
T4 = datetime(2026, 1, 1, 12, 0, 0)
T5 = datetime(2026, 1, 1, 13, 0, 0)

# Convention "Z1130, Z1230"
Z1130 = datetime(2026, 1, 1, 11, 30, tzinfo=timezone.utc)
Z1230 = datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc)

# Convention "P1730, P1830" (the same two instants as Z1130, Z1230)
P1730 = datetime(2026, 1, 1, 17, 30, tzinfo=timezone(timedelta(hours=6)))
P1830 = datetime(2026, 1, 1, 18, 30, tzinfo=timezone(timedelta(hours=6)))


# Convention "HIGH_ID": a marker that `mk_entry(id=HIGH_ID)` replaces, at insert
# time, by high_id(db) below: the value depends on the rows and on the sequence
# position at that moment.
class _HighId:
    def __repr__(self):
        return "HIGH_ID"


HIGH_ID = _HighId()


def high_id(db):
    """max(greatest machine_item_ledger.id or 0, last_value of the sequence) + 1000001."""
    max_id = db.execute(select(func.max(MachineItemLedger.__table__.c.id))).scalar() or 0
    last_value = db.execute(text("SELECT last_value FROM machine_item_ledger_id_seq")).scalar()
    return max(max_id, last_value) + 1000001


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows". w2 depends on w1, so ids rise in
# the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "U1, U2 = two profiles rows"
@pytest.fixture
def u1(db):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


# Convention "F1"
@pytest.fixture
def f1(db, w1):
    return _add(db, Factory(workspace_id=w1.id, name="Factory One", abbreviation="F1"))


# Convention "F9"
@pytest.fixture
def f9(db, w2):
    return _add(db, Factory(workspace_id=w2.id, name="Factory Nine", abbreviation="F9"))


# Convention "FD": soft-deleted
@pytest.fixture
def fd(db, w1):
    return _add(db, Factory(workspace_id=w1.id, name="Old Plant", abbreviation="OP", is_deleted=True))


# Convention "M1, M2"
@pytest.fixture
def m1(db, w1, f1):
    return _add(db, Machine(workspace_id=w1.id, factory_id=f1.id, name="Press 1"))


@pytest.fixture
def m2(db, w1, f1):
    return _add(db, Machine(workspace_id=w1.id, factory_id=f1.id, name="Press 2"))


# Convention "MD": soft-deleted
@pytest.fixture
def md(db, w1, f1):
    return _add(db, Machine(workspace_id=w1.id, factory_id=f1.id, name="Press 4", is_deleted=True))


# Convention "MF": live machine of a soft-deleted factory
@pytest.fixture
def mf(db, w1, fd):
    return _add(db, Machine(workspace_id=w1.id, factory_id=fd.id, name="Press 5"))


# Convention "I1, I2"
@pytest.fixture
def i1(db, w1):
    return _add(db, Item(workspace_id=w1.id, name="Bolt", name_normalized="bolt", unit="pcs"))


@pytest.fixture
def i2(db, w1):
    return _add(db, Item(workspace_id=w1.id, name="Nut", name_normalized="nut", unit="pcs"))


# Convention "IR": removed from the catalog
@pytest.fixture
def ir(db, w1):
    return _add(db, Item(workspace_id=w1.id, name="Old Gasket", name_normalized="old gasket", unit="pcs",
                         is_active=False))


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, f1, f9, fd, m1, m2, md, mf, i1, i2, ir):
    return None


# Convention "FULL"
@pytest.fixture
def full(w1, m1, i1, u1):
    return {"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "transaction_type": "manual_add",
            "quantity": 3, "unit_cost": Decimal("2.50"), "total_cost": Decimal("7.50"), "qty_before": 4,
            "qty_after": 7, "source_type": "manual", "performed_by": u1.id}


# --------------------------------------------------------------------------- #
# Conventions -> row builders
# --------------------------------------------------------------------------- #

def _entry_fields(w1, m1, i1, u1, performed_at, columns):
    fields = {"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "transaction_type": "manual_add",
              "quantity": 1, "unit_cost": Decimal("2.00"), "total_cost": Decimal("2.00"), "qty_before": 4,
              "qty_after": 5, "source_type": "manual", "performed_by": u1.id, "performed_at": performed_at}
    fields.update(columns)
    return fields


# Convention "entry": built with MachineItemLedger, inserted and flushed
@pytest.fixture
def mk_entry(db, w1, m1, i1, u1):
    """mk_entry(performed_at=..., **columns) -> MachineItemLedger. Keywords only."""
    def _mk(*, performed_at, **columns):
        fields = _entry_fields(w1, m1, i1, u1, performed_at, columns)
        if fields.get("id") is HIGH_ID:
            fields["id"] = high_id(db)
        return _add(db, MachineItemLedger(**fields))
    return _mk


# The Given "added with db.add(E2) and not flushed"
@pytest.fixture
def mk_pending(db, w1, m1, i1, u1):
    """mk_pending(performed_at=..., **columns) -> an entry added to the session, not flushed."""
    def _mk(*, performed_at, **columns):
        row = MachineItemLedger(**_entry_fields(w1, m1, i1, u1, performed_at, columns))
        db.add(row)
        return row
    return _mk


def mk_n(mk_entry, count):
    """Given "N entries N1 ... Nk, inserted in that order": Nk = entry, performed_at
    T1 + timedelta(minutes=k). Returns {k: Nk}."""
    return {k: mk_entry(performed_at=T1 + timedelta(minutes=k)) for k in range(1, count + 1)}


# Convention "Rolled back": the spy wraps db.commit (still callable, records calls)
@pytest.fixture
def commit_spy(db):
    with patch.object(db, "commit", wraps=db.commit) as spy:
        yield spy


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "ids(result)": the ids in the order returned (the order is part of the check)
def ids(result):
    return [row.id for row in result]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    """Fresh copy of the ledger row `row` from the database, or None if it is gone."""
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(MachineItemLedger).where(MachineItemLedger.id == row_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "count:" lines: rows of machine_item_ledger, with the filter stated
def count_rows(db, **where):
    table = MachineItemLedger.__table__
    stmt = select(func.count()).select_from(table)
    for column, value in where.items():
        stmt = stmt.where(table.c[column] == value)
    return db.execute(stmt).scalar_one()


# Convention "nothing written": row counts of machine_item_ledger, machines, items
# and factories (all workspaces)
def written(db):
    return {
        model.__tablename__: db.execute(select(func.count()).select_from(model.__table__)).scalar_one()
        for model in (MachineItemLedger, Machine, Item, Factory)
    }


# Convention "Statement recorder": the SQL text of every statement the session's
# connection sends while the block runs (`before_cursor_execute` listener).
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
# `MachineItemLedgerDAO.get_by_item`
# --------------------------------------------------------------------------- #

# [claude] MIL-IT-01
def test_mil_it_01__an_entry_of_another_item_is_not_returned(db, w1, i1, i2, mk_entry):
    """MIL-IT-01 — an entry of another item is not returned.
    Rules: `get_by_item` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, item_id=i2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-IT-02
def test_mil_it_02__an_entry_of_another_workspace_with_the_same_item_and_machine_ids_is_not(db, w1, w2, i1, mk_entry):
    """MIL-IT-02 — an entry of another workspace with the same item and machine ids is not returned.
    Rules: `get_by_item` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-IT-03
def test_mil_it_03__the_other_workspace_gets_only_its_own_entry(db, w2, i1, mk_entry):
    """MIL-IT-03 — the other workspace gets only its own entry.
    Rules: `get_by_item` R1"""
    mk_entry(performed_at=T1)
    x9 = mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x9.id]

# [claude] MIL-IT-04
def test_mil_it_04__an_unknown_workspace_id_returns_an_empty_list(db, i1, mk_entry):
    """MIL-IT-04 — an unknown workspace id returns an empty list.
    Rules: `get_by_item` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=MISSING)

    # Then 1
    assert result == []

# [claude] MIL-IT-05
def test_mil_it_05__an_unknown_item_id_returns_an_empty_list(db, w1, mk_entry):
    """MIL-IT-05 — an unknown item id returns an empty list.
    Rules: `get_by_item` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_item(db, item_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-IT-06
def test_mil_it_06__an_item_without_entries_returns_an_empty_list(db, w1, i2, mk_entry):
    """MIL-IT-06 — an item without entries returns an empty list.
    Rules: `get_by_item` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_item(db, item_id=i2.id, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-IT-07
def test_mil_it_07__entries_of_every_machine_transaction_type_and_performer_are_returned(db, w1, u2, m2, i1, mk_entry):
    """MIL-IT-07 — entries of every machine, transaction type and performer are returned.
    Rules: `get_by_item` R2"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, machine_id=m2.id)
    e3 = mk_entry(performed_at=T3, transaction_type="consumption")
    e4 = mk_entry(performed_at=T4, performed_by=u2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e4.id, e3.id, e2.id, e1.id]

# [claude] MIL-IT-08
def test_mil_it_08__item_id_0_returns_an_empty_list_and_raises_nothing(db, w1, mk_entry):
    """MIL-IT-08 — item_id 0 returns an empty list and raises nothing.
    Rules: `get_by_item` R3"""
    mk_entry(performed_at=T1)

    result = dao.get_by_item(db, item_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-IT-09
def test_mil_it_09__item_id_none_returns_an_empty_list_and_raises_nothing(db, w1, mk_entry):
    """MIL-IT-09 — item_id None returns an empty list and raises nothing.
    Rules: `get_by_item` R3"""
    mk_entry(performed_at=T1)

    result = dao.get_by_item(db, item_id=None, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-IT-10
def test_mil_it_10__an_entry_not_yet_flushed_is_not_seen(db, w1, i1, mk_entry, mk_pending):
    """MIL-IT-10 — an entry not yet flushed is not seen.
    Rules: `get_by_item` R9"""
    e1 = mk_entry(performed_at=T1)
    mk_pending(performed_at=T2)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-IT-11
def test_mil_it_11__returns_a_list_of_ledger_rows_newest_first_whatever_the_insertion_order(db, w1, i1, mk_entry):
    """MIL-IT-11 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing.
    Rules: `get_by_item` R4, R9, Returns"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert isinstance(result[0], MachineItemLedger)
    # Then 3
    assert ids(result) == [e2.id, e3.id, e1.id]
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-IT-12
def test_mil_it_12__skip_1_and_limit_1_return_exactly_the_middle_entry(db, w1, i1, mk_entry):
    """MIL-IT-12 — skip 1 and limit 1 return exactly the middle entry.
    Rules: `get_by_item` R5"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]

# [claude] MIL-IT-13
def test_mil_it_13__limit_2_returns_the_two_newest_entries(db, w1, i1, mk_entry):
    """MIL-IT-13 — limit 2 returns the two newest entries.
    Rules: `get_by_item` R5"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [e2.id, e3.id]

# [claude] MIL-IT-14
def test_mil_it_14__limit_1_returns_only_the_newest_entry(db, w1, i1, mk_entry):
    """MIL-IT-14 — limit 1 returns only the newest entry.
    Rules: `get_by_item` R5"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-IT-15
def test_mil_it_15__skip_one_below_the_number_of_entries_returns_the_oldest_entry(db, w1, i1, mk_entry):
    """MIL-IT-15 — skip one below the number of entries returns the oldest entry.
    Rules: `get_by_item` R5"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-IT-16
def test_mil_it_16__skip_equal_to_the_number_of_entries_returns_an_empty_list(db, w1, i1, mk_entry):
    """MIL-IT-16 — skip equal to the number of entries returns an empty list.
    Rules: `get_by_item` R6"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []

# [claude] MIL-IT-17
def test_mil_it_17__skip_past_the_number_of_entries_returns_an_empty_list(db, w1, i1, mk_entry):
    """MIL-IT-17 — skip past the number of entries returns an empty list.
    Rules: `get_by_item` R6"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id, skip=4)

    # Then 1
    assert result == []

# [claude] MIL-IT-18
def test_mil_it_18__limit_0_returns_an_empty_list(db, w1, i1, mk_entry):
    """MIL-IT-18 — limit 0 returns an empty list.
    Rules: `get_by_item` R6"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []

# [claude] MIL-IT-19
def test_mil_it_19__paging_counts_matching_entries_only_newer_entries_left_out_by_the(db, w1, w2, i1, i2, mk_entry):
    """MIL-IT-19 — paging counts matching entries only: newer entries left out by the filters use no place on the page.
    Rules: `get_by_item` R5"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)
    mk_entry(performed_at=T3, item_id=i2.id)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-IT-20
def test_mil_it_20__by_default_at_most_the_100_newest_of_101_entries_are_returned_the(db, w1, i1, mk_entry):
    """MIL-IT-20 — by default at most the 100 newest of 101 entries are returned; the oldest is missing.
    Rules: `get_by_item` R5"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 1, -1)]
    # Then 3
    assert n[1].id not in ids(result)

# [claude] MIL-IT-21
def test_mil_it_21__exactly_100_entries_are_all_returned_by_default(db, w1, i1, mk_entry):
    """MIL-IT-21 — exactly 100 entries are all returned by default.
    Rules: `get_by_item` R5"""
    n = mk_n(mk_entry, 100)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(100, 0, -1)]

# [claude] MIL-IT-22
def test_mil_it_22__limit_101_returns_all_101_entries_the_method_has_no_upper_cap(db, w1, i1, mk_entry):
    """MIL-IT-22 — limit 101 returns all 101 entries: the method has no upper cap.
    Rules: `get_by_item` R5"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 0, -1)]

# [claude] MIL-IT-23
def test_mil_it_23__a_negative_limit_makes_the_database_reject_the_query(db, w1, i1, mk_entry):
    """MIL-IT-23 — a negative limit makes the database reject the query.
    Rules: `get_by_item` R7, Errors row 1"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-IT-24
def test_mil_it_24__a_negative_skip_makes_the_database_reject_the_query(db, w1, i1, mk_entry):
    """MIL-IT-24 — a negative skip makes the database reject the query.
    Rules: `get_by_item` R7, Errors row 2"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-IT-25
def test_mil_it_25__tied_entries_are_each_returned_once_between_the_newer_and_the_older(db, w1, i1, mk_entry):
    """MIL-IT-25 — tied entries are each returned once, between the newer and the older entry.
    Rules: `get_by_item` R4"""
    o = mk_entry(performed_at=T1)
    n = mk_entry(performed_at=T3)
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 5
    # Then 2
    assert result[0].id == n.id
    # Then 3
    assert result[-1].id == o.id
    # Then 4
    assert sorted(ids(result)[1:4]) == sorted([b.id, c.id, a.id])

# [claude] MIL-IT-26
@pytest.mark.xfail(strict=False, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_mil_it_26__entries_with_the_same_performed_at_come_back_by_id_highest_first(db, w1, i1, mk_entry):
    """MIL-IT-26 — entries with the same performed_at come back by id, highest first.
    Rules: `get_by_item` R4a"""
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == sorted([b.id, c.id, a.id])
    # Then 2
    assert ids(result) == [c.id, a.id, b.id]

# [claude] MIL-IT-27
@pytest.mark.xfail(strict=True, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_mil_it_27__the_query_asks_the_database_for_performed_at_newest_first_then_id(db, w1, i1, mk_entry):
    """MIL-IT-27 — the query asks the database for performed_at newest first, then id highest first.
    Rules: `get_by_item` R4a"""
    e1 = mk_entry(performed_at=T1)

    with StatementRecorder(db) as rec:
        result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)
    [sql] = rec.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_item_ledger.performed_at DESC" in order_part
    # Then 4
    assert "machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part

# [claude] MIL-IT-28
def test_mil_it_28__an_entry_of_a_soft_deleted_machine_is_returned(db, w1, md, i1, mk_entry):
    """MIL-IT-28 — an entry of a soft-deleted machine is returned.
    Rules: `get_by_item` R8"""
    e1 = mk_entry(performed_at=T1, machine_id=md.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-IT-29
def test_mil_it_29__an_entry_of_a_live_machine_in_a_soft_deleted_factory_is_returned(db, w1, mf, i1, mk_entry):
    """MIL-IT-29 — an entry of a live machine in a soft-deleted factory is returned.
    Rules: `get_by_item` R8"""
    e1 = mk_entry(performed_at=T1, machine_id=mf.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-IT-30
def test_mil_it_30__an_entry_of_a_removed_item_is_returned(db, w1, ir, mk_entry):
    """MIL-IT-30 — an entry of a removed item is returned.
    Rules: `get_by_item` R8"""
    e1 = mk_entry(performed_at=T1, item_id=ir.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_item(db, item_id=ir.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# --------------------------------------------------------------------------- #
# `MachineItemLedgerDAO.get_by_machine_and_item`
# --------------------------------------------------------------------------- #

# [claude] MIL-MI-01
def test_mil_mi_01__an_entry_of_another_machine_is_not_returned(db, w1, m1, m2, i1, mk_entry):
    """MIL-MI-01 — an entry of another machine is not returned.
    Rules: `get_by_machine_and_item` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, machine_id=m2.id)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-MI-02
def test_mil_mi_02__an_entry_of_another_item_is_not_returned(db, w1, m1, i1, i2, mk_entry):
    """MIL-MI-02 — an entry of another item is not returned.
    Rules: `get_by_machine_and_item` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, item_id=i2.id)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-MI-03
def test_mil_mi_03__an_entry_of_another_workspace_with_the_same_machine_and_item_ids_is_not(db, w1, w2, m1, i1, mk_entry):
    """MIL-MI-03 — an entry of another workspace with the same machine and item ids is not returned.
    Rules: `get_by_machine_and_item` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-MI-04
def test_mil_mi_04__the_other_workspace_gets_only_its_own_entry(db, w2, m1, i1, mk_entry):
    """MIL-MI-04 — the other workspace gets only its own entry.
    Rules: `get_by_machine_and_item` R1"""
    mk_entry(performed_at=T1)
    x9 = mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x9.id]

# [claude] MIL-MI-05
def test_mil_mi_05__a_machine_and_an_item_that_have_entries_but_none_together_return_an(db, w1, m1, m2, i1, i2, mk_entry):
    """MIL-MI-05 — a machine and an item that have entries, but none together, return an empty list.
    Rules: `get_by_machine_and_item` R1"""
    mk_entry(performed_at=T1, item_id=i2.id)
    mk_entry(performed_at=T2, machine_id=m2.id)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-MI-06
def test_mil_mi_06__an_unknown_machine_id_returns_an_empty_list(db, w1, i1, mk_entry):
    """MIL-MI-06 — an unknown machine id returns an empty list.
    Rules: `get_by_machine_and_item` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_machine_and_item(db, machine_id=MISSING, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-MI-07
def test_mil_mi_07__an_unknown_item_id_returns_an_empty_list(db, w1, m1, mk_entry):
    """MIL-MI-07 — an unknown item id returns an empty list.
    Rules: `get_by_machine_and_item` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-MI-08
def test_mil_mi_08__an_unknown_workspace_id_returns_an_empty_list(db, m1, i1, mk_entry):
    """MIL-MI-08 — an unknown workspace id returns an empty list.
    Rules: `get_by_machine_and_item` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=MISSING)

    # Then 1
    assert result == []

# [claude] MIL-MI-09
def test_mil_mi_09__machine_id_0_returns_an_empty_list(db, w1, i1, mk_entry):
    """MIL-MI-09 — machine_id 0 returns an empty list.
    Rules: `get_by_machine_and_item` R2"""
    mk_entry(performed_at=T1)

    result = dao.get_by_machine_and_item(db, machine_id=0, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-MI-10
def test_mil_mi_10__item_id_0_returns_an_empty_list(db, w1, m1, mk_entry):
    """MIL-MI-10 — item_id 0 returns an empty list.
    Rules: `get_by_machine_and_item` R2"""
    mk_entry(performed_at=T1)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-MI-11
def test_mil_mi_11__returns_a_list_of_ledger_rows_newest_first_whatever_the_insertion_order(db, w1, m1, i1, mk_entry):
    """MIL-MI-11 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing.
    Rules: `get_by_machine_and_item` R3, R6, Returns"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert isinstance(result[0], MachineItemLedger)
    # Then 3
    assert ids(result) == [e2.id, e3.id, e1.id]
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-MI-12
def test_mil_mi_12__skip_1_and_limit_1_return_exactly_the_middle_entry(db, w1, m1, i1, mk_entry):
    """MIL-MI-12 — skip 1 and limit 1 return exactly the middle entry.
    Rules: `get_by_machine_and_item` R4"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]

# [claude] MIL-MI-13
def test_mil_mi_13__limit_2_returns_the_two_newest_entries(db, w1, m1, i1, mk_entry):
    """MIL-MI-13 — limit 2 returns the two newest entries.
    Rules: `get_by_machine_and_item` R4"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [e2.id, e3.id]

# [claude] MIL-MI-14
def test_mil_mi_14__limit_1_returns_only_the_newest_entry(db, w1, m1, i1, mk_entry):
    """MIL-MI-14 — limit 1 returns only the newest entry.
    Rules: `get_by_machine_and_item` R4"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-MI-15
def test_mil_mi_15__skip_one_below_the_number_of_entries_returns_the_oldest_entry(db, w1, m1, i1, mk_entry):
    """MIL-MI-15 — skip one below the number of entries returns the oldest entry.
    Rules: `get_by_machine_and_item` R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-MI-16
def test_mil_mi_16__skip_equal_to_the_number_of_entries_returns_an_empty_list(db, w1, m1, i1, mk_entry):
    """MIL-MI-16 — skip equal to the number of entries returns an empty list.
    Rules: `get_by_machine_and_item` R4"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []

# [claude] MIL-MI-17
def test_mil_mi_17__skip_past_the_number_of_entries_returns_an_empty_list(db, w1, m1, i1, mk_entry):
    """MIL-MI-17 — skip past the number of entries returns an empty list.
    Rules: `get_by_machine_and_item` R4"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id, skip=4)

    # Then 1
    assert result == []

# [claude] MIL-MI-18
def test_mil_mi_18__limit_0_returns_an_empty_list(db, w1, m1, i1, mk_entry):
    """MIL-MI-18 — limit 0 returns an empty list.
    Rules: `get_by_machine_and_item` R4"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []

# [claude] MIL-MI-19
def test_mil_mi_19__paging_counts_matching_entries_only_newer_entries_left_out_by_the(db, w1, w2, m1, m2, i1, mk_entry):
    """MIL-MI-19 — paging counts matching entries only: newer entries left out by the filters use no place on the page.
    Rules: `get_by_machine_and_item` R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)
    mk_entry(performed_at=T3, machine_id=m2.id)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-MI-20
def test_mil_mi_20__by_default_at_most_the_100_newest_of_101_entries_are_returned_the(db, w1, m1, i1, mk_entry):
    """MIL-MI-20 — by default at most the 100 newest of 101 entries are returned; the oldest is missing.
    Rules: `get_by_machine_and_item` R4"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 1, -1)]
    # Then 3
    assert n[1].id not in ids(result)

# [claude] MIL-MI-21
def test_mil_mi_21__exactly_100_entries_are_all_returned_by_default(db, w1, m1, i1, mk_entry):
    """MIL-MI-21 — exactly 100 entries are all returned by default.
    Rules: `get_by_machine_and_item` R4"""
    n = mk_n(mk_entry, 100)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(100, 0, -1)]

# [claude] MIL-MI-22
def test_mil_mi_22__limit_101_returns_all_101_entries_the_method_has_no_upper_cap(db, w1, m1, i1, mk_entry):
    """MIL-MI-22 — limit 101 returns all 101 entries: the method has no upper cap.
    Rules: `get_by_machine_and_item` R4"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 0, -1)]

# [claude] MIL-MI-23
def test_mil_mi_23__a_negative_limit_makes_the_database_reject_the_query(db, w1, m1, i1, mk_entry):
    """MIL-MI-23 — a negative limit makes the database reject the query.
    Rules: `get_by_machine_and_item` R4, Errors (as get_by_item)"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-MI-24
def test_mil_mi_24__a_negative_skip_makes_the_database_reject_the_query(db, w1, m1, i1, mk_entry):
    """MIL-MI-24 — a negative skip makes the database reject the query.
    Rules: `get_by_machine_and_item` R4, Errors (as get_by_item)"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-MI-25
def test_mil_mi_25__tied_entries_are_each_returned_once_between_the_newer_and_the_older(db, w1, m1, i1, mk_entry):
    """MIL-MI-25 — tied entries are each returned once, between the newer and the older entry.
    Rules: `get_by_machine_and_item` R3"""
    o = mk_entry(performed_at=T1)
    n = mk_entry(performed_at=T3)
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 5
    # Then 2
    assert result[0].id == n.id
    # Then 3
    assert result[-1].id == o.id
    # Then 4
    assert sorted(ids(result)[1:4]) == sorted([b.id, c.id, a.id])

# [claude] MIL-MI-26
@pytest.mark.xfail(strict=False, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_mil_mi_26__entries_with_the_same_performed_at_come_back_by_id_highest_first(db, w1, m1, i1, mk_entry):
    """MIL-MI-26 — entries with the same performed_at come back by id, highest first.
    Rules: `get_by_machine_and_item` R3a"""
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == sorted([b.id, c.id, a.id])
    # Then 2
    assert ids(result) == [c.id, a.id, b.id]

# [claude] MIL-MI-27
@pytest.mark.xfail(strict=True, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_mil_mi_27__the_query_asks_the_database_for_performed_at_newest_first_then_id(db, w1, m1, i1, mk_entry):
    """MIL-MI-27 — the query asks the database for performed_at newest first, then id highest first.
    Rules: `get_by_machine_and_item` R3a"""
    e1 = mk_entry(performed_at=T1)

    with StatementRecorder(db) as rec:
        result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    [sql] = rec.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_item_ledger.performed_at DESC" in order_part
    # Then 4
    assert "machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part

# [claude] MIL-MI-28
def test_mil_mi_28__an_entry_of_a_soft_deleted_machine_is_returned(db, w1, md, i1, mk_entry):
    """MIL-MI-28 — an entry of a soft-deleted machine is returned.
    Rules: `get_by_machine_and_item` R5"""
    e1 = mk_entry(performed_at=T1, machine_id=md.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_machine_and_item(db, machine_id=md.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-MI-29
def test_mil_mi_29__an_entry_of_a_live_machine_in_a_soft_deleted_factory_is_returned(db, w1, mf, i1, mk_entry):
    """MIL-MI-29 — an entry of a live machine in a soft-deleted factory is returned.
    Rules: `get_by_machine_and_item` R5"""
    e1 = mk_entry(performed_at=T1, machine_id=mf.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_machine_and_item(db, machine_id=mf.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-MI-30
def test_mil_mi_30__an_entry_of_a_removed_item_is_returned(db, w1, m1, ir, mk_entry):
    """MIL-MI-30 — an entry of a removed item is returned.
    Rules: `get_by_machine_and_item` R5"""
    e1 = mk_entry(performed_at=T1, item_id=ir.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=ir.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1


# [claude] MIL-MI-31
def test_mil_mi_31__a_pending_entry_stays_pending_and_is_not_seen_the_call_writes_nothing(db, w1, m1, i1, mk_entry, mk_pending):
    """MIL-MI-31 — a pending entry stays pending and is not seen: the call writes nothing.
    Rules: `get_by_machine_and_item` R6"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_pending(performed_at=T2)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert e2 in db.new

# --------------------------------------------------------------------------- #
# `MachineItemLedgerDAO.get_by_transaction_type`
# --------------------------------------------------------------------------- #

# [claude] MIL-TT-01
def test_mil_tt_01__purchase_order_finds_its_entry_and_not_an_entry_of_purchase_return(db, w1, mk_entry):
    """MIL-TT-01 — "purchase_order" finds its entry and not an entry of "purchase_return".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="purchase_order")
    mk_entry(performed_at=T2, transaction_type="purchase_return")

    result = dao.get_by_transaction_type(db, transaction_type="purchase_order", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-02
def test_mil_tt_02__purchase_return_finds_its_entry_and_not_an_entry_of_purchase_order(db, w1, mk_entry):
    """MIL-TT-02 — "purchase_return" finds its entry and not an entry of "purchase_order".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="purchase_return")
    mk_entry(performed_at=T2, transaction_type="purchase_order")

    result = dao.get_by_transaction_type(db, transaction_type="purchase_return", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-03
def test_mil_tt_03__manual_add_finds_its_entry_and_not_an_entry_of_consumption(db, w1, mk_entry):
    """MIL-TT-03 — "manual_add" finds its entry and not an entry of "consumption".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="manual_add")
    mk_entry(performed_at=T2, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-04
def test_mil_tt_04__inventory_adjustment_finds_its_entry_and_not_an_entry_of_cost_adjustment(db, w1, mk_entry):
    """MIL-TT-04 — "inventory_adjustment" finds its entry and not an entry of "cost_adjustment".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="inventory_adjustment")
    mk_entry(performed_at=T2, transaction_type="cost_adjustment")

    result = dao.get_by_transaction_type(db, transaction_type="inventory_adjustment", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-05
def test_mil_tt_05__transfer_in_finds_its_entry_and_not_an_entry_of_transfer_out(db, w1, mk_entry):
    """MIL-TT-05 — "transfer_in" finds its entry and not an entry of "transfer_out".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="transfer_in")
    mk_entry(performed_at=T2, transaction_type="transfer_out")

    result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-06
def test_mil_tt_06__transfer_out_finds_its_entry_and_not_an_entry_of_transfer_in(db, w1, mk_entry):
    """MIL-TT-06 — "transfer_out" finds its entry and not an entry of "transfer_in".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="transfer_out")
    mk_entry(performed_at=T2, transaction_type="transfer_in")

    result = dao.get_by_transaction_type(db, transaction_type="transfer_out", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-07
def test_mil_tt_07__consumption_finds_its_entry_and_not_an_entry_of_consumption_reversal(db, w1, mk_entry):
    """MIL-TT-07 — "consumption" finds its entry and not an entry of "consumption_reversal".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="consumption")
    mk_entry(performed_at=T2, transaction_type="consumption_reversal")

    result = dao.get_by_transaction_type(db, transaction_type="consumption", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-08
def test_mil_tt_08__consumption_reversal_finds_its_entry_and_not_an_entry_of_consumption(db, w1, mk_entry):
    """MIL-TT-08 — "consumption_reversal" finds its entry and not an entry of "consumption".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="consumption_reversal")
    mk_entry(performed_at=T2, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type="consumption_reversal", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-09
def test_mil_tt_09__work_order_install_finds_its_entry_and_not_an_entry_of_work_order(db, w1, mk_entry):
    """MIL-TT-09 — "work_order_install" finds its entry and not an entry of "work_order_borrow_returned".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="work_order_install")
    mk_entry(performed_at=T2, transaction_type="work_order_borrow_returned")

    result = dao.get_by_transaction_type(db, transaction_type="work_order_install", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-10
def test_mil_tt_10__work_order_replace_out_finds_its_entry_and_not_an_entry_of_work_order(db, w1, mk_entry):
    """MIL-TT-10 — "work_order_replace_out" finds its entry and not an entry of "work_order_replace_in".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="work_order_replace_out")
    mk_entry(performed_at=T2, transaction_type="work_order_replace_in")

    result = dao.get_by_transaction_type(db, transaction_type="work_order_replace_out", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-11
def test_mil_tt_11__work_order_replace_in_finds_its_entry_and_not_an_entry_of_work_order(db, w1, mk_entry):
    """MIL-TT-11 — "work_order_replace_in" finds its entry and not an entry of "work_order_replace_out".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="work_order_replace_in")
    mk_entry(performed_at=T2, transaction_type="work_order_replace_out")

    result = dao.get_by_transaction_type(db, transaction_type="work_order_replace_in", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-12
def test_mil_tt_12__work_order_borrow_returned_finds_its_entry_and_not_an_entry_of_work(db, w1, mk_entry):
    """MIL-TT-12 — "work_order_borrow_returned" finds its entry and not an entry of "work_order_install".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="work_order_borrow_returned")
    mk_entry(performed_at=T2, transaction_type="work_order_install")

    result = dao.get_by_transaction_type(db, transaction_type="work_order_borrow_returned", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-13
def test_mil_tt_13__damaged_finds_its_entry_and_not_an_entry_of_consumption(db, w1, mk_entry):
    """MIL-TT-13 — "damaged" finds its entry and not an entry of "consumption".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="damaged")
    mk_entry(performed_at=T2, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type="damaged", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-14
def test_mil_tt_14__cost_adjustment_finds_its_entry_and_not_an_entry_of_inventory_adjustment(db, w1, mk_entry):
    """MIL-TT-14 — "cost_adjustment" finds its entry and not an entry of "inventory_adjustment".
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="cost_adjustment")
    mk_entry(performed_at=T2, transaction_type="inventory_adjustment")

    result = dao.get_by_transaction_type(db, transaction_type="cost_adjustment", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-15
def test_mil_tt_15__the_type_in_capitals_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-15 — the type in capitals returns an empty list.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type="CONSUMPTION", workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-TT-16
def test_mil_tt_16__the_type_with_a_capital_first_letter_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-16 — the type with a capital first letter returns an empty list.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type="Consumption", workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-TT-17
def test_mil_tt_17__a_trailing_space_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-17 — a trailing space returns an empty list.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type="consumption ", workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-TT-18
def test_mil_tt_18__a_leading_space_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-18 — a leading space returns an empty list.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type=" consumption", workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-TT-19
def test_mil_tt_19__a_in_the_type_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-19 — a % in the type returns an empty list.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type="consum%", workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-TT-20
def test_mil_tt_20__an_in_the_type_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-20 — an _ in the type returns an empty list.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type="consu_ption", workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-TT-21
def test_mil_tt_21__a_prefix_of_the_type_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-21 — a prefix of the type returns an empty list.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type="consum", workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-TT-22
def test_mil_tt_22__an_unknown_type_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-22 — an unknown type returns an empty list.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type="no_such_type", workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-TT-23
def test_mil_tt_23__an_empty_type_returns_an_empty_list_and_raises_nothing(db, w1, mk_entry):
    """MIL-TT-23 — an empty type returns an empty list and raises nothing.
    Rules: `get_by_transaction_type` R2"""
    mk_entry(performed_at=T1)

    result = dao.get_by_transaction_type(db, transaction_type="", workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-TT-24
def test_mil_tt_24__a_type_of_none_returns_an_empty_list_and_raises_nothing(db, w1, mk_entry):
    """MIL-TT-24 — a type of None returns an empty list and raises nothing.
    Rules: `get_by_transaction_type` R2"""
    mk_entry(performed_at=T1)

    result = dao.get_by_transaction_type(db, transaction_type=None, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-TT-25
def test_mil_tt_25__an_entry_of_another_workspace_is_not_returned(db, w1, w2, mk_entry):
    """MIL-TT-25 — an entry of another workspace is not returned.
    Rules: `get_by_transaction_type` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-26
def test_mil_tt_26__the_other_workspace_gets_only_its_own_entry(db, w2, mk_entry):
    """MIL-TT-26 — the other workspace gets only its own entry.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1)
    x9 = mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x9.id]

# [claude] MIL-TT-27
def test_mil_tt_27__an_unknown_workspace_id_returns_an_empty_list(db, mk_entry):
    """MIL-TT-27 — an unknown workspace id returns an empty list.
    Rules: `get_by_transaction_type` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=MISSING)

    # Then 1
    assert result == []

# [claude] MIL-TT-28
def test_mil_tt_28__with_no_machine_and_no_item_entries_of_every_machine_and_item_of_the(db, w1, m2, i2, mk_entry):
    """MIL-TT-28 — with no machine and no item, entries of every machine and item of the workspace are returned.
    Rules: `get_by_transaction_type` R3"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, item_id=i2.id)
    e3 = mk_entry(performed_at=T3, machine_id=m2.id)
    e4 = mk_entry(performed_at=T4, machine_id=m2.id, item_id=i2.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e4.id, e3.id, e2.id, e1.id]

# [claude] MIL-TT-29
def test_mil_tt_29__a_given_machine_narrows_to_that_machine_for_every_item(db, w1, m1, m2, i2, mk_entry):
    """MIL-TT-29 — a given machine narrows to that machine, for every item.
    Rules: `get_by_transaction_type` R4"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, item_id=i2.id)
    mk_entry(performed_at=T3, machine_id=m2.id)
    mk_entry(performed_at=T4, machine_id=m2.id, item_id=i2.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [e2.id, e1.id]

# [claude] MIL-TT-30
def test_mil_tt_30__a_given_item_narrows_to_that_item_on_every_machine(db, w1, m2, i1, i2, mk_entry):
    """MIL-TT-30 — a given item narrows to that item, on every machine.
    Rules: `get_by_transaction_type` R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, item_id=i2.id)
    e3 = mk_entry(performed_at=T3, machine_id=m2.id)
    mk_entry(performed_at=T4, machine_id=m2.id, item_id=i2.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, item_id=i1.id)

    # Then 1
    assert ids(result) == [e3.id, e1.id]

# [claude] MIL-TT-31
def test_mil_tt_31__a_given_machine_and_item_combine_with_and(db, w1, m2, i1, i2, mk_entry):
    """MIL-TT-31 — a given machine and item combine with AND.
    Rules: `get_by_transaction_type` R4"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, item_id=i2.id)
    e3 = mk_entry(performed_at=T3, machine_id=m2.id)
    mk_entry(performed_at=T4, machine_id=m2.id, item_id=i2.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, machine_id=m2.id, item_id=i1.id)

    # Then 1
    assert ids(result) == [e3.id]

# [claude] MIL-TT-32
def test_mil_tt_32__machine_and_item_without_a_common_entry_return_an_empty_list(db, w1, m1, m2, i2, mk_entry):
    """MIL-TT-32 — machine and item without a common entry return an empty list.
    Rules: `get_by_transaction_type` R4"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, machine_id=m2.id, item_id=i2.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, machine_id=m1.id, item_id=i2.id)

    # Then 1
    assert result == []

# [claude] MIL-TT-33
def test_mil_tt_33__machine_filter_and_type_filter_combine_another_type_on_that_machine_is(db, w1, m1, mk_entry):
    """MIL-TT-33 — machine filter and type filter combine: another type on that machine is left out.
    Rules: `get_by_transaction_type` R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, transaction_type="consumption")

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, machine_id=m1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-34
def test_mil_tt_34__machine_id_0_filters_like_any_integer_and_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-34 — machine_id 0 filters like any integer and returns an empty list.
    Rules: `get_by_transaction_type` R4a"""
    mk_entry(performed_at=T1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, machine_id=0)

    # Then 1
    assert result == []

# [claude] MIL-TT-35
def test_mil_tt_35__item_id_0_filters_like_any_integer_and_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-35 — item_id 0 filters like any integer and returns an empty list.
    Rules: `get_by_transaction_type` R4a"""
    mk_entry(performed_at=T1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, item_id=0)

    # Then 1
    assert result == []

# [claude] MIL-TT-36
def test_mil_tt_36__returns_a_list_of_ledger_rows_newest_first_whatever_the_insertion_order(db, w1, mk_entry):
    """MIL-TT-36 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing.
    Rules: `get_by_transaction_type` R5, R8, Returns"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert isinstance(result[0], MachineItemLedger)
    # Then 3
    assert ids(result) == [e2.id, e3.id, e1.id]
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-TT-37
def test_mil_tt_37__skip_1_and_limit_1_return_exactly_the_middle_entry(db, w1, mk_entry):
    """MIL-TT-37 — skip 1 and limit 1 return exactly the middle entry.
    Rules: `get_by_transaction_type` R6"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]

# [claude] MIL-TT-38
def test_mil_tt_38__limit_2_returns_the_two_newest_entries(db, w1, mk_entry):
    """MIL-TT-38 — limit 2 returns the two newest entries.
    Rules: `get_by_transaction_type` R6"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [e2.id, e3.id]

# [claude] MIL-TT-39
def test_mil_tt_39__limit_1_returns_only_the_newest_entry(db, w1, mk_entry):
    """MIL-TT-39 — limit 1 returns only the newest entry.
    Rules: `get_by_transaction_type` R6"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-TT-40
def test_mil_tt_40__skip_one_below_the_number_of_entries_returns_the_oldest_entry(db, w1, mk_entry):
    """MIL-TT-40 — skip one below the number of entries returns the oldest entry.
    Rules: `get_by_transaction_type` R6"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, skip=2)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-41
def test_mil_tt_41__skip_equal_to_the_number_of_entries_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-41 — skip equal to the number of entries returns an empty list.
    Rules: `get_by_transaction_type` R6"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []

# [claude] MIL-TT-42
def test_mil_tt_42__skip_past_the_number_of_entries_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-42 — skip past the number of entries returns an empty list.
    Rules: `get_by_transaction_type` R6"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, skip=4)

    # Then 1
    assert result == []

# [claude] MIL-TT-43
def test_mil_tt_43__limit_0_returns_an_empty_list(db, w1, mk_entry):
    """MIL-TT-43 — limit 0 returns an empty list.
    Rules: `get_by_transaction_type` R6"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []

# [claude] MIL-TT-44
def test_mil_tt_44__paging_counts_matching_entries_only_newer_entries_left_out_by_the(db, w1, w2, mk_entry):
    """MIL-TT-44 — paging counts matching entries only: newer entries left out by the filters use no place on the page.
    Rules: `get_by_transaction_type` R6"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)
    mk_entry(performed_at=T3, transaction_type="consumption")
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-TT-45
def test_mil_tt_45__by_default_at_most_the_100_newest_of_101_entries_are_returned_the(db, w1, mk_entry):
    """MIL-TT-45 — by default at most the 100 newest of 101 entries are returned; the oldest is missing.
    Rules: `get_by_transaction_type` R6"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 1, -1)]
    # Then 3
    assert n[1].id not in ids(result)

# [claude] MIL-TT-46
def test_mil_tt_46__exactly_100_entries_are_all_returned_by_default(db, w1, mk_entry):
    """MIL-TT-46 — exactly 100 entries are all returned by default.
    Rules: `get_by_transaction_type` R6"""
    n = mk_n(mk_entry, 100)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(100, 0, -1)]

# [claude] MIL-TT-47
def test_mil_tt_47__limit_101_returns_all_101_entries_the_method_has_no_upper_cap(db, w1, mk_entry):
    """MIL-TT-47 — limit 101 returns all 101 entries: the method has no upper cap.
    Rules: `get_by_transaction_type` R6"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 0, -1)]

# [claude] MIL-TT-48
def test_mil_tt_48__a_negative_limit_makes_the_database_reject_the_query(db, w1, mk_entry):
    """MIL-TT-48 — a negative limit makes the database reject the query.
    Rules: `get_by_transaction_type` R6, Errors (as get_by_item)"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-TT-49
def test_mil_tt_49__a_negative_skip_makes_the_database_reject_the_query(db, w1, mk_entry):
    """MIL-TT-49 — a negative skip makes the database reject the query.
    Rules: `get_by_transaction_type` R6, Errors (as get_by_item)"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-TT-50
def test_mil_tt_50__tied_entries_are_each_returned_once_between_the_newer_and_the_older(db, w1, mk_entry):
    """MIL-TT-50 — tied entries are each returned once, between the newer and the older entry.
    Rules: `get_by_transaction_type` R5"""
    o = mk_entry(performed_at=T1)
    n = mk_entry(performed_at=T3)
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert len(result) == 5
    # Then 2
    assert result[0].id == n.id
    # Then 3
    assert result[-1].id == o.id
    # Then 4
    assert sorted(ids(result)[1:4]) == sorted([b.id, c.id, a.id])

# [claude] MIL-TT-51
@pytest.mark.xfail(strict=False, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_mil_tt_51__entries_with_the_same_performed_at_come_back_by_id_highest_first(db, w1, mk_entry):
    """MIL-TT-51 — entries with the same performed_at come back by id, highest first.
    Rules: `get_by_transaction_type` R5a"""
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == sorted([b.id, c.id, a.id])
    # Then 2
    assert ids(result) == [c.id, a.id, b.id]

# [claude] MIL-TT-52
@pytest.mark.xfail(strict=True, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_mil_tt_52__the_query_asks_the_database_for_performed_at_newest_first_then_id(db, w1, mk_entry):
    """MIL-TT-52 — the query asks the database for performed_at newest first, then id highest first.
    Rules: `get_by_transaction_type` R5a"""
    e1 = mk_entry(performed_at=T1)

    with StatementRecorder(db) as rec:
        result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)
    [sql] = rec.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_item_ledger.performed_at DESC" in order_part
    # Then 4
    assert "machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part

# [claude] MIL-TT-53
def test_mil_tt_53__an_entry_of_a_soft_deleted_machine_is_returned_with_no_machine_filter(db, w1, md, mk_entry):
    """MIL-TT-53 — an entry of a soft-deleted machine is returned with no machine filter.
    Rules: `get_by_transaction_type` R7"""
    e1 = mk_entry(performed_at=T1, machine_id=md.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-TT-54
def test_mil_tt_54__an_entry_of_a_soft_deleted_machine_is_returned_with_that_machine_as(db, w1, md, mk_entry):
    """MIL-TT-54 — an entry of a soft-deleted machine is returned with that machine as filter.
    Rules: `get_by_transaction_type` R7"""
    e1 = mk_entry(performed_at=T1, machine_id=md.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, machine_id=md.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-TT-55
def test_mil_tt_55__an_entry_of_a_live_machine_in_a_soft_deleted_factory_is_returned(db, w1, mf, mk_entry):
    """MIL-TT-55 — an entry of a live machine in a soft-deleted factory is returned.
    Rules: `get_by_transaction_type` R7"""
    e1 = mk_entry(performed_at=T1, machine_id=mf.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, machine_id=mf.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-TT-56
def test_mil_tt_56__an_entry_of_a_removed_item_is_returned_with_no_item_filter(db, w1, ir, mk_entry):
    """MIL-TT-56 — an entry of a removed item is returned with no item filter.
    Rules: `get_by_transaction_type` R7"""
    e1 = mk_entry(performed_at=T1, item_id=ir.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-TT-57
def test_mil_tt_57__an_entry_of_a_removed_item_is_returned_with_that_item_as_filter(db, w1, ir, mk_entry):
    """MIL-TT-57 — an entry of a removed item is returned with that item as filter.
    Rules: `get_by_transaction_type` R7"""
    e1 = mk_entry(performed_at=T1, item_id=ir.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id, item_id=ir.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1


# [claude] MIL-TT-58
def test_mil_tt_58__a_pending_entry_stays_pending_and_is_not_seen_the_call_writes_nothing(db, w1, mk_entry, mk_pending):
    """MIL-TT-58 — a pending entry stays pending and is not seen: the call writes nothing.
    Rules: `get_by_transaction_type` R8"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_pending(performed_at=T2)

    result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert e2 in db.new

# --------------------------------------------------------------------------- #
# `MachineItemLedgerDAO.get_by_date_range`
# --------------------------------------------------------------------------- #

# [claude] MIL-DR-01
def test_mil_dr_01__both_bounds_are_inclusive_range_t1_to_t3_returns_all_three_entries(db, w1, mk_entry):
    """MIL-DR-01 — both bounds are inclusive: range T1 to T3 returns all three entries.
    Rules: `get_by_date_range` R1"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3)

    # Then 1
    assert ids(result) == [e2.id, e3.id, e1.id]

# [claude] MIL-DR-02
def test_mil_dr_02__bounds_one_microsecond_inside_keep_only_the_middle_entry(db, w1, mk_entry):
    """MIL-DR-02 — bounds one microsecond inside keep only the middle entry.
    Rules: `get_by_date_range` R1"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 1, 1, 9, 0, 0, 1), end_date=datetime(2026, 1, 1, 10, 59, 59, 999999))

    # Then 1
    assert ids(result) == [e3.id]

# [claude] MIL-DR-03
def test_mil_dr_03__start_exactly_at_the_entry_keeps_it(db, w1, mk_entry):
    """MIL-DR-03 — start exactly at the entry keeps it.
    Rules: `get_by_date_range` R1"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T2, end_date=T5)

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-DR-04
def test_mil_dr_04__start_one_microsecond_after_the_entry_leaves_it_out(db, w1, mk_entry):
    """MIL-DR-04 — start one microsecond after the entry leaves it out.
    Rules: `get_by_date_range` R1"""
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 1, 1, 10, 0, 0, 1), end_date=T5)

    # Then 1
    assert result == []

# [claude] MIL-DR-05
def test_mil_dr_05__end_exactly_at_the_entry_keeps_it(db, w1, mk_entry):
    """MIL-DR-05 — end exactly at the entry keeps it.
    Rules: `get_by_date_range` R1"""
    e2 = mk_entry(performed_at=T2)
    mk_entry(performed_at=T3)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T2)

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-DR-06
def test_mil_dr_06__end_one_microsecond_before_the_entry_leaves_it_out(db, w1, mk_entry):
    """MIL-DR-06 — end one microsecond before the entry leaves it out.
    Rules: `get_by_date_range` R1"""
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=datetime(2026, 1, 1, 9, 59, 59, 999999))

    # Then 1
    assert result == []

# [claude] MIL-DR-07
def test_mil_dr_07__a_midnight_end_date_stays_exact_at_the_dao_that_day_s_entry_is_left_out(db, w1, mk_entry):
    """MIL-DR-07 — a midnight end date stays exact at the DAO: that day's entry is left out.
    Rules: `get_by_date_range` R1"""
    e1 = mk_entry(performed_at=datetime(2026, 9, 29, 10, 0, 0))
    mk_entry(performed_at=datetime(2026, 9, 30, 10, 0, 0))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 9, 29, 0, 0, 0), end_date=datetime(2026, 9, 30, 0, 0, 0))

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-08
def test_mil_dr_08__an_end_at_the_last_microsecond_of_the_day_keeps_that_day_s_entry(db, w1, mk_entry):
    """MIL-DR-08 — an end at the last microsecond of the day keeps that day's entry.
    Rules: `get_by_date_range` R1"""
    e1 = mk_entry(performed_at=datetime(2026, 9, 29, 10, 0, 0))
    e2 = mk_entry(performed_at=datetime(2026, 9, 30, 10, 0, 0))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 9, 29, 0, 0, 0), end_date=datetime(2026, 9, 30, 23, 59, 59, 999999))

    # Then 1
    assert ids(result) == [e2.id, e1.id]

# [claude] MIL-DR-09
def test_mil_dr_09__equal_bounds_return_exactly_the_entry_at_that_instant(db, w1, mk_entry):
    """MIL-DR-09 — equal bounds return exactly the entry at that instant.
    Rules: `get_by_date_range` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T2, end_date=T2)

    # Then 1
    assert ids(result) == [e3.id]

# [claude] MIL-DR-10
def test_mil_dr_10__equal_bounds_at_an_instant_without_an_entry_return_an_empty_list(db, w1, mk_entry):
    """MIL-DR-10 — equal bounds at an instant without an entry return an empty list.
    Rules: `get_by_date_range` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 1, 1, 9, 30, 0, 0), end_date=datetime(2026, 1, 1, 9, 30, 0, 0))

    # Then 1
    assert result == []

# [claude] MIL-DR-11
def test_mil_dr_11__a_start_later_than_the_end_returns_an_empty_list_and_raises_nothing(db, w1, mk_entry):
    """MIL-DR-11 — a start later than the end returns an empty list and raises nothing.
    Rules: `get_by_date_range` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T3, end_date=T1)

    # Then 1
    assert result == []

# [claude] MIL-DR-12
def test_mil_dr_12__naive_bounds_are_compared_as_stored_utc_under_the_session_zone_america(db, w1, mk_entry):
    """MIL-DR-12 — naive bounds are compared as stored UTC under the session zone America/New_York.
    Rules: `get_by_date_range` R3"""
    e1 = mk_entry(performed_at=T4)
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 1, 1, 11, 30, 0, 0), end_date=datetime(2026, 1, 1, 12, 30, 0, 0))

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-13
def test_mil_dr_13__naive_bounds_are_compared_as_stored_utc_under_the_session_zone_asia(db, w1, mk_entry):
    """MIL-DR-13 — naive bounds are compared as stored UTC under the session zone Asia/Dhaka.
    Rules: `get_by_date_range` R3"""
    e1 = mk_entry(performed_at=T4)
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 1, 1, 11, 30, 0, 0), end_date=datetime(2026, 1, 1, 12, 30, 0, 0))

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-14
def test_mil_dr_14__naive_bounds_are_compared_as_stored_utc_under_the_session_zone_utc(db, w1, mk_entry):
    """MIL-DR-14 — naive bounds are compared as stored UTC under the session zone UTC.
    Rules: `get_by_date_range` R3"""
    e1 = mk_entry(performed_at=T4)
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 1, 1, 11, 30, 0, 0), end_date=datetime(2026, 1, 1, 12, 30, 0, 0))

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-15
def test_mil_dr_15__naive_bounds_that_miss_the_stored_time_return_an_empty_list_under_a(db, w1, mk_entry):
    """MIL-DR-15 — naive bounds that miss the stored time return an empty list under a shifted session zone.
    Rules: `get_by_date_range` R3"""
    mk_entry(performed_at=T4)
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 1, 1, 16, 30, 0, 0), end_date=datetime(2026, 1, 1, 17, 30, 0, 0))

    # Then 1
    assert result == []

# [claude] MIL-DR-16
@pytest.mark.xfail(strict=True, reason="BUG-992: Ledger date filter with a time zone depends on the database's time-zone setting")
def test_mil_dr_16__aware_bounds_in_utc_find_the_entry_under_the_session_zone_america_new(db, w1, mk_entry):
    """MIL-DR-16 — aware bounds in UTC find the entry under the session zone America/New_York.
    Rules: `get_by_date_range` R3a"""
    e1 = mk_entry(performed_at=T4)
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=Z1130, end_date=Z1230)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-17
@pytest.mark.xfail(strict=True, reason="BUG-992: Ledger date filter with a time zone depends on the database's time-zone setting")
def test_mil_dr_17__aware_bounds_in_utc_find_the_entry_under_the_session_zone_asia_dhaka(db, w1, mk_entry):
    """MIL-DR-17 — aware bounds in UTC find the entry under the session zone Asia/Dhaka.
    Rules: `get_by_date_range` R3a"""
    e1 = mk_entry(performed_at=T4)
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=Z1130, end_date=Z1230)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-18
@pytest.mark.xfail(strict=True, reason="BUG-992: Ledger date filter with a time zone depends on the database's time-zone setting")
def test_mil_dr_18__aware_bounds_with_an_offset_find_the_entry_under_a_session_zone_of(db, w1, mk_entry):
    """MIL-DR-18 — aware bounds with an offset find the entry under a session zone of America/New_York.
    Rules: `get_by_date_range` R3a"""
    e1 = mk_entry(performed_at=T4)
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=P1730, end_date=P1830)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-19
@pytest.mark.xfail(strict=True, reason="BUG-992: Ledger date filter with a time zone depends on the database's time-zone setting")
def test_mil_dr_19__aware_bounds_do_not_catch_an_entry_outside_the_utc_window_under_a(db, w1, mk_entry):
    """MIL-DR-19 — aware bounds do not catch an entry outside the UTC window under a shifted session zone.
    Rules: `get_by_date_range` R3a"""
    e1 = mk_entry(performed_at=T4)
    mk_entry(performed_at=datetime(2026, 1, 1, 7, 0, 0, 0))
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=Z1130, end_date=Z1230)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-20
def test_mil_dr_20__control_aware_utc_bounds_find_the_entry_under_the_session_zone_utc(db, w1, mk_entry):
    """MIL-DR-20 — control: aware UTC bounds find the entry under the session zone UTC.
    Rules: `get_by_date_range` R3a"""
    e1 = mk_entry(performed_at=T4)
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=Z1130, end_date=Z1230)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-21
def test_mil_dr_21__control_aware_bounds_with_an_offset_are_converted_not_cut_off_under_the(db, w1, mk_entry):
    """MIL-DR-21 — control: aware bounds with an offset are converted, not cut off, under the session zone UTC.
    Rules: `get_by_date_range` R3a"""
    e1 = mk_entry(performed_at=T4)
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=P1730, end_date=P1830)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-22
def test_mil_dr_22__control_aware_utc_bounds_leave_out_an_entry_outside_the_window_under(db, w1, mk_entry):
    """MIL-DR-22 — control: aware UTC bounds leave out an entry outside the window under the session zone UTC.
    Rules: `get_by_date_range` R3a"""
    mk_entry(performed_at=T5)
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=Z1130, end_date=Z1230)

    # Then 1
    assert result == []

# [claude] MIL-DR-23
def test_mil_dr_23__start_date_none_raises_argumenterror_before_any_query_is_sent(db, w1, mk_entry):
    """MIL-DR-23 — start_date None raises ArgumentError before any query is sent.
    Rules: `get_by_date_range` R4, Errors row 1"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(ArgumentError) as exc:
        with StatementRecorder(db) as rec:
            dao.get_by_date_range(db, workspace_id=w1.id, start_date=None, end_date=T3)
    statements = rec.statements

    # Then 2
    assert str(exc.value).startswith("Only '=', '!=', 'is_()', 'is_not()', 'is_distinct_from()', 'is_not_distinct_from()' operators can be used with None/True/False")
    # Then 3
    assert statements == []
    # Then 4
    assert written(db) == before

# [claude] MIL-DR-24
def test_mil_dr_24__end_date_none_raises_argumenterror_before_any_query_is_sent(db, w1, mk_entry):
    """MIL-DR-24 — end_date None raises ArgumentError before any query is sent.
    Rules: `get_by_date_range` R4, Errors row 1"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(ArgumentError) as exc:
        with StatementRecorder(db) as rec:
            dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=None)
    statements = rec.statements

    # Then 2
    assert str(exc.value).startswith("Only '=', '!=', 'is_()', 'is_not()', 'is_distinct_from()', 'is_not_distinct_from()' operators can be used with None/True/False")
    # Then 3
    assert statements == []
    # Then 4
    assert written(db) == before

# [claude] MIL-DR-25
def test_mil_dr_25__an_entry_of_another_workspace_inside_the_window_is_not_returned(db, w1, w2, mk_entry):
    """MIL-DR-25 — an entry of another workspace inside the window is not returned.
    Rules: `get_by_date_range` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-26
def test_mil_dr_26__the_other_workspace_gets_only_its_own_entry(db, w2, mk_entry):
    """MIL-DR-26 — the other workspace gets only its own entry.
    Rules: `get_by_date_range` R1"""
    mk_entry(performed_at=T1)
    x9 = mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_date_range(db, workspace_id=w2.id, start_date=T1, end_date=T5)

    # Then 1
    assert ids(result) == [x9.id]

# [claude] MIL-DR-27
def test_mil_dr_27__an_unknown_workspace_id_returns_an_empty_list(db, mk_entry):
    """MIL-DR-27 — an unknown workspace id returns an empty list.
    Rules: `get_by_date_range` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_date_range(db, workspace_id=MISSING, start_date=T1, end_date=T5)

    # Then 1
    assert result == []

# [claude] MIL-DR-28
def test_mil_dr_28__with_no_machine_and_no_item_entries_of_every_machine_and_item_in_the(db, w1, m2, i2, mk_entry):
    """MIL-DR-28 — with no machine and no item, entries of every machine and item in the window are returned.
    Rules: `get_by_date_range` R6"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, item_id=i2.id)
    e3 = mk_entry(performed_at=T3, machine_id=m2.id)
    e4 = mk_entry(performed_at=T4, machine_id=m2.id, item_id=i2.id)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5)

    # Then 1
    assert ids(result) == [e4.id, e3.id, e2.id, e1.id]

# [claude] MIL-DR-29
def test_mil_dr_29__a_given_machine_narrows_to_that_machine_for_every_item(db, w1, m1, m2, i2, mk_entry):
    """MIL-DR-29 — a given machine narrows to that machine, for every item.
    Rules: `get_by_date_range` R6"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, item_id=i2.id)
    mk_entry(performed_at=T3, machine_id=m2.id)
    mk_entry(performed_at=T4, machine_id=m2.id, item_id=i2.id)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, machine_id=m1.id)

    # Then 1
    assert ids(result) == [e2.id, e1.id]

# [claude] MIL-DR-30
def test_mil_dr_30__a_given_item_narrows_to_that_item_on_every_machine(db, w1, m2, i1, i2, mk_entry):
    """MIL-DR-30 — a given item narrows to that item, on every machine.
    Rules: `get_by_date_range` R6"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, item_id=i2.id)
    e3 = mk_entry(performed_at=T3, machine_id=m2.id)
    mk_entry(performed_at=T4, machine_id=m2.id, item_id=i2.id)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, item_id=i1.id)

    # Then 1
    assert ids(result) == [e3.id, e1.id]

# [claude] MIL-DR-31
def test_mil_dr_31__a_given_machine_and_item_combine_with_and(db, w1, m2, i1, i2, mk_entry):
    """MIL-DR-31 — a given machine and item combine with AND.
    Rules: `get_by_date_range` R6"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, item_id=i2.id)
    e3 = mk_entry(performed_at=T3, machine_id=m2.id)
    mk_entry(performed_at=T4, machine_id=m2.id, item_id=i2.id)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, machine_id=m2.id, item_id=i1.id)

    # Then 1
    assert ids(result) == [e3.id]

# [claude] MIL-DR-32
def test_mil_dr_32__the_machine_filter_does_not_widen_the_window_that_machine_s_entry(db, w1, m1, mk_entry):
    """MIL-DR-32 — the machine filter does not widen the window: that machine's entry outside it is left out.
    Rules: `get_by_date_range` R6, R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T5)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, machine_id=m1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-33
def test_mil_dr_33__machine_id_0_filters_like_any_integer_and_returns_an_empty_list(db, w1, mk_entry):
    """MIL-DR-33 — machine_id 0 filters like any integer and returns an empty list.
    Rules: `get_by_date_range` R6"""
    mk_entry(performed_at=T1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, machine_id=0)

    # Then 1
    assert result == []

# [claude] MIL-DR-34
def test_mil_dr_34__item_id_0_filters_like_any_integer_and_returns_an_empty_list(db, w1, mk_entry):
    """MIL-DR-34 — item_id 0 filters like any integer and returns an empty list.
    Rules: `get_by_date_range` R6"""
    mk_entry(performed_at=T1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, item_id=0)

    # Then 1
    assert result == []

# [claude] MIL-DR-35
def test_mil_dr_35__returns_a_list_of_ledger_rows_newest_first_whatever_the_insertion_order(db, w1, mk_entry):
    """MIL-DR-35 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing.
    Rules: `get_by_date_range` R5, R8, Returns"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert isinstance(result[0], MachineItemLedger)
    # Then 3
    assert ids(result) == [e2.id, e3.id, e1.id]
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-DR-36
def test_mil_dr_36__skip_1_and_limit_1_return_exactly_the_middle_entry(db, w1, mk_entry):
    """MIL-DR-36 — skip 1 and limit 1 return exactly the middle entry.
    Rules: `get_by_date_range` R6a"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]

# [claude] MIL-DR-37
def test_mil_dr_37__limit_2_returns_the_two_newest_entries(db, w1, mk_entry):
    """MIL-DR-37 — limit 2 returns the two newest entries.
    Rules: `get_by_date_range` R6a"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, limit=2)

    # Then 1
    assert ids(result) == [e2.id, e3.id]

# [claude] MIL-DR-38
def test_mil_dr_38__limit_1_returns_only_the_newest_entry(db, w1, mk_entry):
    """MIL-DR-38 — limit 1 returns only the newest entry.
    Rules: `get_by_date_range` R6a"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, limit=1)

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-DR-39
def test_mil_dr_39__skip_one_below_the_number_of_entries_returns_the_oldest_entry(db, w1, mk_entry):
    """MIL-DR-39 — skip one below the number of entries returns the oldest entry.
    Rules: `get_by_date_range` R6a"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, skip=2)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-40
def test_mil_dr_40__skip_equal_to_the_number_of_entries_returns_an_empty_list(db, w1, mk_entry):
    """MIL-DR-40 — skip equal to the number of entries returns an empty list.
    Rules: `get_by_date_range` R6a"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, skip=3)

    # Then 1
    assert result == []

# [claude] MIL-DR-41
def test_mil_dr_41__skip_past_the_number_of_entries_returns_an_empty_list(db, w1, mk_entry):
    """MIL-DR-41 — skip past the number of entries returns an empty list.
    Rules: `get_by_date_range` R6a"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, skip=4)

    # Then 1
    assert result == []

# [claude] MIL-DR-42
def test_mil_dr_42__limit_0_returns_an_empty_list(db, w1, mk_entry):
    """MIL-DR-42 — limit 0 returns an empty list.
    Rules: `get_by_date_range` R6a"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, limit=0)

    # Then 1
    assert result == []

# [claude] MIL-DR-43
def test_mil_dr_43__paging_counts_matching_entries_only_newer_entries_left_out_by_the(db, w1, w2, mk_entry):
    """MIL-DR-43 — paging counts matching entries only: newer entries left out by the filters use no place on the page.
    Rules: `get_by_date_range` R6a"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)
    mk_entry(performed_at=T4)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T3, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-DR-44
def test_mil_dr_44__by_default_at_most_the_100_newest_of_101_entries_are_returned_the(db, w1, mk_entry):
    """MIL-DR-44 — by default at most the 100 newest of 101 entries are returned; the oldest is missing.
    Rules: `get_by_date_range` R6a"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 1, -1)]
    # Then 3
    assert n[1].id not in ids(result)

# [claude] MIL-DR-45
def test_mil_dr_45__exactly_100_entries_are_all_returned_by_default(db, w1, mk_entry):
    """MIL-DR-45 — exactly 100 entries are all returned by default.
    Rules: `get_by_date_range` R6a"""
    n = mk_n(mk_entry, 100)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(100, 0, -1)]

# [claude] MIL-DR-46
def test_mil_dr_46__limit_101_returns_all_101_entries_the_method_has_no_upper_cap(db, w1, mk_entry):
    """MIL-DR-46 — limit 101 returns all 101 entries: the method has no upper cap.
    Rules: `get_by_date_range` R6a"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 0, -1)]

# [claude] MIL-DR-47
def test_mil_dr_47__a_negative_limit_makes_the_database_reject_the_query(db, w1, mk_entry):
    """MIL-DR-47 — a negative limit makes the database reject the query.
    Rules: `get_by_date_range` R6a, Errors row 2"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-DR-48
def test_mil_dr_48__a_negative_skip_makes_the_database_reject_the_query(db, w1, mk_entry):
    """MIL-DR-48 — a negative skip makes the database reject the query.
    Rules: `get_by_date_range` R6a, Errors row 2"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-DR-49
def test_mil_dr_49__tied_entries_are_each_returned_once_between_the_newer_and_the_older(db, w1, mk_entry):
    """MIL-DR-49 — tied entries are each returned once, between the newer and the older entry.
    Rules: `get_by_date_range` R5"""
    o = mk_entry(performed_at=T1)
    n = mk_entry(performed_at=T3)
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5)

    # Then 1
    assert len(result) == 5
    # Then 2
    assert result[0].id == n.id
    # Then 3
    assert result[-1].id == o.id
    # Then 4
    assert sorted(ids(result)[1:4]) == sorted([b.id, c.id, a.id])

# [claude] MIL-DR-50
@pytest.mark.xfail(strict=False, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_mil_dr_50__entries_with_the_same_performed_at_come_back_by_id_highest_first(db, w1, mk_entry):
    """MIL-DR-50 — entries with the same performed_at come back by id, highest first.
    Rules: `get_by_date_range` R5a"""
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5)

    # Then 1
    assert sorted(ids(result)) == sorted([b.id, c.id, a.id])
    # Then 2
    assert ids(result) == [c.id, a.id, b.id]

# [claude] MIL-DR-51
@pytest.mark.xfail(strict=True, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_mil_dr_51__the_query_asks_the_database_for_performed_at_newest_first_then_id(db, w1, mk_entry):
    """MIL-DR-51 — the query asks the database for performed_at newest first, then id highest first.
    Rules: `get_by_date_range` R5a"""
    e1 = mk_entry(performed_at=T1)

    with StatementRecorder(db) as rec:
        result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5)
    [sql] = rec.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_item_ledger.performed_at DESC" in order_part
    # Then 4
    assert "machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part

# [claude] MIL-DR-52
def test_mil_dr_52__an_entry_of_a_soft_deleted_machine_is_returned_with_no_machine_filter(db, w1, md, mk_entry):
    """MIL-DR-52 — an entry of a soft-deleted machine is returned with no machine filter.
    Rules: `get_by_date_range` R7"""
    e1 = mk_entry(performed_at=T1, machine_id=md.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-DR-53
def test_mil_dr_53__an_entry_of_a_soft_deleted_machine_is_returned_with_that_machine_as(db, w1, md, mk_entry):
    """MIL-DR-53 — an entry of a soft-deleted machine is returned with that machine as filter.
    Rules: `get_by_date_range` R7"""
    e1 = mk_entry(performed_at=T1, machine_id=md.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, machine_id=md.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-DR-54
def test_mil_dr_54__an_entry_of_a_live_machine_in_a_soft_deleted_factory_is_returned(db, w1, mf, mk_entry):
    """MIL-DR-54 — an entry of a live machine in a soft-deleted factory is returned.
    Rules: `get_by_date_range` R7"""
    e1 = mk_entry(performed_at=T1, machine_id=mf.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, machine_id=mf.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-DR-55
def test_mil_dr_55__an_entry_of_a_removed_item_is_returned_with_no_item_filter(db, w1, ir, mk_entry):
    """MIL-DR-55 — an entry of a removed item is returned with no item filter.
    Rules: `get_by_date_range` R7"""
    e1 = mk_entry(performed_at=T1, item_id=ir.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-DR-56
def test_mil_dr_56__an_entry_of_a_removed_item_is_returned_with_that_item_as_filter(db, w1, ir, mk_entry):
    """MIL-DR-56 — an entry of a removed item is returned with that item as filter.
    Rules: `get_by_date_range` R7"""
    e1 = mk_entry(performed_at=T1, item_id=ir.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T5, item_id=ir.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-DR-57
@pytest.mark.xfail(strict=True, reason="BUG-992: Ledger date filter with a time zone depends on the database's time-zone setting")
def test_mil_dr_57__aware_bounds_keep_only_the_entry_in_the_utc_window_under_the_session(db, w1, mk_entry):
    """MIL-DR-57 — aware bounds keep only the entry in the UTC window under the session zone Asia/Dhaka.
    Rules: `get_by_date_range` R3a"""
    mk_entry(performed_at=datetime(2026, 1, 1, 7, 0, 0))
    e2 = mk_entry(performed_at=T4)
    mk_entry(performed_at=datetime(2026, 1, 1, 18, 0, 0))
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=Z1130, end_date=Z1230)

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-DR-58
@pytest.mark.xfail(strict=True, reason="BUG-992: Ledger date filter with a time zone depends on the database's time-zone setting")
def test_mil_dr_58__aware_start_naive_end_the_naive_bound_stays_as_given_under_america_new(db, w1, mk_entry):
    """MIL-DR-58 — aware start, naive end: the naive bound stays as given under America/New_York.
    Rules: `get_by_date_range` R3a"""
    mk_entry(performed_at=datetime(2026, 1, 1, 7, 0, 0))
    e2 = mk_entry(performed_at=T4)
    mk_entry(performed_at=datetime(2026, 1, 1, 18, 0, 0))
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=Z1130, end_date=datetime(2026, 1, 1, 12, 30, 0, 0))

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-DR-59
@pytest.mark.xfail(strict=True, reason="BUG-992: Ledger date filter with a time zone depends on the database's time-zone setting")
def test_mil_dr_59__naive_start_aware_end_the_naive_bound_stays_as_given_under_america_new(db, w1, mk_entry):
    """MIL-DR-59 — naive start, aware end: the naive bound stays as given under America/New_York.
    Rules: `get_by_date_range` R3a"""
    mk_entry(performed_at=datetime(2026, 1, 1, 7, 0, 0))
    e2 = mk_entry(performed_at=T4)
    mk_entry(performed_at=datetime(2026, 1, 1, 18, 0, 0))
    db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=datetime(2026, 1, 1, 11, 30, 0, 0), end_date=Z1230)

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-DR-60
def test_mil_dr_60__control_aware_bounds_keep_only_the_entry_in_the_utc_window_under_the(db, w1, mk_entry):
    """MIL-DR-60 — control: aware bounds keep only the entry in the UTC window under the session zone UTC.
    Rules: `get_by_date_range` R3a"""
    mk_entry(performed_at=datetime(2026, 1, 1, 7, 0, 0))
    e2 = mk_entry(performed_at=T4)
    mk_entry(performed_at=datetime(2026, 1, 1, 18, 0, 0))
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=Z1130, end_date=Z1230)

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-DR-61
def test_mil_dr_61__control_an_aware_start_with_a_naive_end_keeps_only_the_entry_in_the(db, w1, mk_entry):
    """MIL-DR-61 — control: an aware start with a naive end keeps only the entry in the window under the session zone UTC.
    Rules: `get_by_date_range` R3a"""
    mk_entry(performed_at=datetime(2026, 1, 1, 7, 0, 0))
    e2 = mk_entry(performed_at=T4)
    mk_entry(performed_at=datetime(2026, 1, 1, 18, 0, 0))
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=Z1130, end_date=datetime(2026, 1, 1, 12, 30, 0, 0))

    # Then 1
    assert ids(result) == [e2.id]


# [claude] MIL-DR-62
def test_mil_dr_62__a_pending_entry_stays_pending_and_is_not_seen_the_call_writes_nothing(db, w1, mk_entry, mk_pending):
    """MIL-DR-62 — a pending entry stays pending and is not seen: the call writes nothing.
    Rules: `get_by_date_range` R8"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_pending(performed_at=T2)

    result = dao.get_by_date_range(db, workspace_id=w1.id, start_date=T1, end_date=T2)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert e2 in db.new

# --------------------------------------------------------------------------- #
# `MachineItemLedgerDAO.get_by_machine`
# --------------------------------------------------------------------------- #

# [claude] MIL-MA-01
def test_mil_ma_01__entries_of_every_item_and_transaction_type_of_the_machine_are_returned(db, w1, m1, i2, mk_entry):
    """MIL-MA-01 — entries of every item and transaction type of the machine are returned.
    Rules: `get_by_machine` R1"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, item_id=i2.id)
    e3 = mk_entry(performed_at=T3, transaction_type="consumption")

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e3.id, e2.id, e1.id]

# [claude] MIL-MA-02
def test_mil_ma_02__an_entry_of_another_machine_is_not_returned(db, w1, m1, m2, mk_entry):
    """MIL-MA-02 — an entry of another machine is not returned.
    Rules: `get_by_machine` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, machine_id=m2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-MA-03
def test_mil_ma_03__an_entry_with_that_machine_id_in_another_workspace_is_not_returned(db, w1, w2, m1, mk_entry):
    """MIL-MA-03 — an entry with that machine id in another workspace is not returned.
    Rules: `get_by_machine` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-MA-04
def test_mil_ma_04__the_other_workspace_gets_only_its_own_entry(db, w2, m1, mk_entry):
    """MIL-MA-04 — the other workspace gets only its own entry.
    Rules: `get_by_machine` R1"""
    mk_entry(performed_at=T1)
    x9 = mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x9.id]

# [claude] MIL-MA-05
def test_mil_ma_05__an_unknown_workspace_id_returns_an_empty_list(db, m1, mk_entry):
    """MIL-MA-05 — an unknown workspace id returns an empty list.
    Rules: `get_by_machine` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=MISSING)

    # Then 1
    assert result == []

# [claude] MIL-MA-06
def test_mil_ma_06__machine_id_0_returns_an_empty_list(db, w1, mk_entry):
    """MIL-MA-06 — machine_id 0 returns an empty list.
    Rules: `get_by_machine` R2"""
    mk_entry(performed_at=T1)

    result = dao.get_by_machine(db, machine_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-MA-07
def test_mil_ma_07__an_unknown_machine_id_returns_an_empty_list(db, w1, mk_entry):
    """MIL-MA-07 — an unknown machine id returns an empty list.
    Rules: `get_by_machine` R2"""
    mk_entry(performed_at=T1)

    result = dao.get_by_machine(db, machine_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-MA-08
def test_mil_ma_08__a_machine_with_no_entries_returns_an_empty_list(db, w1, m2, mk_entry):
    """MIL-MA-08 — a machine with no entries returns an empty list.
    Rules: `get_by_machine` R2"""
    mk_entry(performed_at=T1)

    result = dao.get_by_machine(db, machine_id=m2.id, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-MA-09
def test_mil_ma_09__returns_a_list_of_ledger_rows_newest_first_whatever_the_insertion_order(db, w1, m1, mk_entry):
    """MIL-MA-09 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing.
    Rules: `get_by_machine` R3, R6, Returns"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert isinstance(result[0], MachineItemLedger)
    # Then 3
    assert ids(result) == [e2.id, e3.id, e1.id]
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-MA-10
def test_mil_ma_10__skip_1_and_limit_1_return_exactly_the_middle_entry(db, w1, m1, mk_entry):
    """MIL-MA-10 — skip 1 and limit 1 return exactly the middle entry.
    Rules: `get_by_machine` R4"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]

# [claude] MIL-MA-11
def test_mil_ma_11__limit_2_returns_the_two_newest_entries(db, w1, m1, mk_entry):
    """MIL-MA-11 — limit 2 returns the two newest entries.
    Rules: `get_by_machine` R4"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [e2.id, e3.id]

# [claude] MIL-MA-12
def test_mil_ma_12__limit_1_returns_only_the_newest_entry(db, w1, m1, mk_entry):
    """MIL-MA-12 — limit 1 returns only the newest entry.
    Rules: `get_by_machine` R4"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-MA-13
def test_mil_ma_13__skip_one_below_the_number_of_entries_returns_the_oldest_entry(db, w1, m1, mk_entry):
    """MIL-MA-13 — skip one below the number of entries returns the oldest entry.
    Rules: `get_by_machine` R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-MA-14
def test_mil_ma_14__skip_equal_to_the_number_of_entries_returns_an_empty_list(db, w1, m1, mk_entry):
    """MIL-MA-14 — skip equal to the number of entries returns an empty list.
    Rules: `get_by_machine` R4"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []

# [claude] MIL-MA-15
def test_mil_ma_15__skip_past_the_number_of_entries_returns_an_empty_list(db, w1, m1, mk_entry):
    """MIL-MA-15 — skip past the number of entries returns an empty list.
    Rules: `get_by_machine` R4"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=4)

    # Then 1
    assert result == []

# [claude] MIL-MA-16
def test_mil_ma_16__limit_0_returns_an_empty_list(db, w1, m1, mk_entry):
    """MIL-MA-16 — limit 0 returns an empty list.
    Rules: `get_by_machine` R4"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []

# [claude] MIL-MA-17
def test_mil_ma_17__paging_counts_matching_entries_only_newer_entries_left_out_by_the(db, w1, w2, m1, m2, mk_entry):
    """MIL-MA-17 — paging counts matching entries only: newer entries left out by the filters use no place on the page.
    Rules: `get_by_machine` R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)
    mk_entry(performed_at=T3, machine_id=m2.id)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-MA-18
def test_mil_ma_18__by_default_at_most_the_100_newest_of_101_entries_are_returned_the(db, w1, m1, mk_entry):
    """MIL-MA-18 — by default at most the 100 newest of 101 entries are returned; the oldest is missing.
    Rules: `get_by_machine` R4"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 1, -1)]
    # Then 3
    assert n[1].id not in ids(result)

# [claude] MIL-MA-19
def test_mil_ma_19__exactly_100_entries_are_all_returned_by_default(db, w1, m1, mk_entry):
    """MIL-MA-19 — exactly 100 entries are all returned by default.
    Rules: `get_by_machine` R4"""
    n = mk_n(mk_entry, 100)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(100, 0, -1)]

# [claude] MIL-MA-20
def test_mil_ma_20__limit_101_returns_all_101_entries_the_method_has_no_upper_cap(db, w1, m1, mk_entry):
    """MIL-MA-20 — limit 101 returns all 101 entries: the method has no upper cap.
    Rules: `get_by_machine` R4"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 0, -1)]

# [claude] MIL-MA-21
def test_mil_ma_21__a_negative_limit_makes_the_database_reject_the_query(db, w1, m1, mk_entry):
    """MIL-MA-21 — a negative limit makes the database reject the query.
    Rules: `get_by_machine` R4, Errors (as get_by_item)"""
    mk_entry(performed_at=T1)
    before = written(db)

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
    assert written(db) == before

# [claude] MIL-MA-22
def test_mil_ma_22__a_negative_skip_makes_the_database_reject_the_query(db, w1, m1, mk_entry):
    """MIL-MA-22 — a negative skip makes the database reject the query.
    Rules: `get_by_machine` R4, Errors (as get_by_item)"""
    mk_entry(performed_at=T1)
    before = written(db)

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
    assert written(db) == before

# [claude] MIL-MA-23
def test_mil_ma_23__tied_entries_are_each_returned_once_between_the_newer_and_the_older(db, w1, m1, mk_entry):
    """MIL-MA-23 — tied entries are each returned once, between the newer and the older entry.
    Rules: `get_by_machine` R3"""
    o = mk_entry(performed_at=T1)
    n = mk_entry(performed_at=T3)
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 5
    # Then 2
    assert result[0].id == n.id
    # Then 3
    assert result[-1].id == o.id
    # Then 4
    assert sorted(ids(result)[1:4]) == sorted([b.id, c.id, a.id])

# [claude] MIL-MA-24
@pytest.mark.xfail(strict=False, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_mil_ma_24__entries_with_the_same_performed_at_come_back_by_id_highest_first(db, w1, m1, mk_entry):
    """MIL-MA-24 — entries with the same performed_at come back by id, highest first.
    Rules: `get_by_machine` R3a"""
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == sorted([b.id, c.id, a.id])
    # Then 2
    assert ids(result) == [c.id, a.id, b.id]

# [claude] MIL-MA-25
@pytest.mark.xfail(strict=True, reason="BUG-640: Ledger lists ordered by performed_at only; ties in no fixed order")
def test_mil_ma_25__the_query_asks_the_database_for_performed_at_newest_first_then_id(db, w1, m1, mk_entry):
    """MIL-MA-25 — the query asks the database for performed_at newest first, then id highest first.
    Rules: `get_by_machine` R3a"""
    e1 = mk_entry(performed_at=T1)

    with StatementRecorder(db) as rec:
        result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)
    [sql] = rec.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_item_ledger.performed_at DESC" in order_part
    # Then 4
    assert "machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part

# [claude] MIL-MA-26
def test_mil_ma_26__an_entry_of_a_soft_deleted_machine_is_returned(db, w1, md, mk_entry):
    """MIL-MA-26 — an entry of a soft-deleted machine is returned.
    Rules: `get_by_machine` R5"""
    e1 = mk_entry(performed_at=T1, machine_id=md.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_machine(db, machine_id=md.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-MA-27
def test_mil_ma_27__an_entry_of_a_live_machine_in_a_soft_deleted_factory_is_returned(db, w1, mf, mk_entry):
    """MIL-MA-27 — an entry of a live machine in a soft-deleted factory is returned.
    Rules: `get_by_machine` R5"""
    e1 = mk_entry(performed_at=T1, machine_id=mf.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_machine(db, machine_id=mf.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-MA-28
def test_mil_ma_28__an_entry_of_a_removed_item_is_returned(db, w1, m1, ir, mk_entry):
    """MIL-MA-28 — an entry of a removed item is returned.
    Rules: `get_by_machine` R5"""
    e1 = mk_entry(performed_at=T1, item_id=ir.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1


# [claude] MIL-MA-29
def test_mil_ma_29__a_pending_entry_stays_pending_and_is_not_seen_the_call_writes_nothing(db, w1, m1, mk_entry, mk_pending):
    """MIL-MA-29 — a pending entry stays pending and is not seen: the call writes nothing.
    Rules: `get_by_machine` R6"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_pending(performed_at=T2)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert e2 in db.new

# --------------------------------------------------------------------------- #
# `MachineItemLedgerDAO.calculate_balance`
# --------------------------------------------------------------------------- #

# [claude] MIL-BAL-01
def test_mil_bal_01__with_no_entry_the_result_is_the_tuple_0_0_00(db, w1, m1, i1):
    """MIL-BAL-01 — with no entry the result is the tuple (0, 0.00).
    Rules: `calculate_balance` R1, Returns"""
    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, tuple)
    # Then 2
    assert result == (0, Decimal("0.00"))
    # Then 3
    assert str(result[1]) == "0.00"

# [claude] MIL-BAL-02
def test_mil_bal_02__the_latest_entry_s_quantity_and_value_are_returned_nothing_is_summed(db, w1, m1, i1, mk_entry):
    """MIL-BAL-02 — the latest entry's quantity and value are returned; nothing is summed.
    Rules: `calculate_balance` R2, R7, Returns"""
    mk_entry(performed_at=T1, qty_after=30, value_after=Decimal("210.00"))
    e2 = mk_entry(performed_at=T3, qty_after=20, value_after=Decimal("120.00"))
    mk_entry(performed_at=T2, qty_after=10, value_after=Decimal("40.00"))
    before = written(db)
    before_e2 = snap(db, e2)

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, tuple)
    # Then 2
    assert isinstance(result[0], int)
    # Then 3
    assert isinstance(result[1], Decimal)
    # Then 4
    assert result == (20, Decimal("120.00"))
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, e2) == before_e2

# [claude] MIL-BAL-03
def test_mil_bal_03__the_latest_entry_wins_when_it_has_the_lowest_id(db, w1, m1, i1, mk_entry):
    """MIL-BAL-03 — the latest entry wins when it has the lowest id.
    Rules: `calculate_balance` R2"""
    mk_entry(performed_at=T3, qty_after=20, value_after=Decimal("120.00"))
    mk_entry(performed_at=T1, qty_after=30, value_after=Decimal("210.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (20, Decimal("120.00"))

# [claude] MIL-BAL-04
def test_mil_bal_04__the_latest_entry_wins_when_it_has_the_highest_id(db, w1, m1, i1, mk_entry):
    """MIL-BAL-04 — the latest entry wins when it has the highest id.
    Rules: `calculate_balance` R2"""
    mk_entry(performed_at=T1, qty_after=30, value_after=Decimal("210.00"))
    mk_entry(performed_at=T3, qty_after=20, value_after=Decimal("120.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (20, Decimal("120.00"))

# [claude] MIL-BAL-05
def test_mil_bal_05__negative_stored_values_are_returned_as_they_are(db, w1, m1, i1, mk_entry):
    """MIL-BAL-05 — negative stored values are returned as they are.
    Rules: `calculate_balance` R2"""
    mk_entry(performed_at=T1, qty_after=-3, value_after=Decimal("-12.50"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (-3, Decimal("-12.50"))

# [claude] MIL-BAL-06
def test_mil_bal_06__an_emptied_machine_a_latest_quantity_of_0_is_returned_not_treated_as_no(db, w1, m1, i1, mk_entry):
    """MIL-BAL-06 — an emptied machine: a latest quantity of 0 is returned, not treated as no entry.
    Rules: `calculate_balance` R2"""
    mk_entry(performed_at=T1, qty_after=30, value_after=Decimal("210.00"))
    mk_entry(performed_at=T2, qty_after=0, value_after=Decimal("7.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (0, Decimal("7.00"))

# [claude] MIL-BAL-07
def test_mil_bal_07__an_empty_value_after_gives_0_00_and_keeps_qty_after(db, w1, m1, i1, mk_entry):
    """MIL-BAL-07 — an empty value_after gives 0.00 and keeps qty_after.
    Rules: `calculate_balance` R3"""
    mk_entry(performed_at=T1, qty_after=5, value_after=None)

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (5, Decimal("0.00"))
    # Then 2
    assert isinstance(result[1], Decimal)

# [claude] MIL-BAL-08
def test_mil_bal_08__a_stored_value_after_of_0_gives_0_00_and_keeps_qty_after(db, w1, m1, i1, mk_entry):
    """MIL-BAL-08 — a stored value_after of 0 gives 0.00 and keeps qty_after.
    Rules: `calculate_balance` R3"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("0"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (5, Decimal("0.00"))

# [claude] MIL-BAL-09
def test_mil_bal_09__an_empty_value_on_the_latest_entry_does_not_fall_back_to_an_earlier(db, w1, m1, i1, mk_entry):
    """MIL-BAL-09 — an empty value on the latest entry does not fall back to an earlier entry.
    Rules: `calculate_balance` R3, R2"""
    mk_entry(performed_at=T1, qty_after=30, value_after=Decimal("210.00"))
    mk_entry(performed_at=T2, qty_after=5, value_after=None)

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (5, Decimal("0.00"))

# [claude] MIL-BAL-10
def test_mil_bal_10__tied_entries_the_result_is_the_figures_of_one_of_them_never_of_an_older(db, w1, m1, i1, mk_entry):
    """MIL-BAL-10 — tied entries: the result is the figures of one of them, never of an older entry.
    Rules: `calculate_balance` R2"""
    mk_entry(performed_at=T1, qty_after=1, value_after=Decimal("1.00"))
    mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result in [(15, Decimal("150.00")), (10, Decimal("100.00")), (99, Decimal("990.00"))]

# [claude] MIL-BAL-11
@pytest.mark.xfail(strict=False, reason="BUG-641: 'Latest entry' balance lookups pick an arbitrary row on a timestamp tie")
def test_mil_bal_11__among_tied_entries_the_greatest_id_decides_the_balance(db, w1, m1, i1, mk_entry):
    """MIL-BAL-11 — among tied entries the greatest id decides the balance.
    Rules: `calculate_balance` R4"""
    mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result in [(15, Decimal("150.00")), (10, Decimal("100.00")), (99, Decimal("990.00"))]
    # Then 2
    assert result == (10, Decimal("100.00"))

# [claude] MIL-BAL-12
@pytest.mark.xfail(strict=True, reason="BUG-641: 'Latest entry' balance lookups pick an arbitrary row on a timestamp tie")
def test_mil_bal_12__the_query_asks_the_database_for_performed_at_newest_first_then_id(db, w1, m1, i1, mk_entry):
    """MIL-BAL-12 — the query asks the database for performed_at newest first, then id highest first.
    Rules: `calculate_balance` R4"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))

    with StatementRecorder(db) as rec:
        result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    [sql] = rec.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert result == (5, Decimal("10.00"))
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_item_ledger.performed_at DESC" in order_part
    # Then 4
    assert "machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part

# [claude] MIL-BAL-13
def test_mil_bal_13__a_newer_entry_of_another_machine_does_not_change_the_result(db, w1, m1, m2, i1, mk_entry):
    """MIL-BAL-13 — a newer entry of another machine does not change the result.
    Rules: `calculate_balance` R5"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))
    mk_entry(performed_at=T2, machine_id=m2.id, qty_after=9, value_after=Decimal("99.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (5, Decimal("10.00"))

# [claude] MIL-BAL-14
def test_mil_bal_14__when_only_an_entry_of_another_machine_exists_the_result_is_0_0_00(db, w1, m1, m2, i1, mk_entry):
    """MIL-BAL-14 — when only an entry of another machine exists the result is (0, 0.00).
    Rules: `calculate_balance` R5, R1"""
    mk_entry(performed_at=T2, machine_id=m2.id, qty_after=9, value_after=Decimal("99.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (0, Decimal("0.00"))

# [claude] MIL-BAL-15
def test_mil_bal_15__a_newer_entry_of_another_item_does_not_change_the_result(db, w1, m1, i1, i2, mk_entry):
    """MIL-BAL-15 — a newer entry of another item does not change the result.
    Rules: `calculate_balance` R5"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))
    mk_entry(performed_at=T2, item_id=i2.id, qty_after=9, value_after=Decimal("99.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (5, Decimal("10.00"))

# [claude] MIL-BAL-16
def test_mil_bal_16__when_only_an_entry_of_another_item_exists_the_result_is_0_0_00(db, w1, m1, i1, i2, mk_entry):
    """MIL-BAL-16 — when only an entry of another item exists the result is (0, 0.00).
    Rules: `calculate_balance` R5, R1"""
    mk_entry(performed_at=T2, item_id=i2.id, qty_after=9, value_after=Decimal("99.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (0, Decimal("0.00"))

# [claude] MIL-BAL-17
def test_mil_bal_17__a_newer_entry_of_another_workspace_does_not_change_the_result(db, w1, w2, m1, i1, mk_entry):
    """MIL-BAL-17 — a newer entry of another workspace does not change the result.
    Rules: `calculate_balance` R5"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))
    mk_entry(performed_at=T2, workspace_id=w2.id, qty_after=9, value_after=Decimal("99.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (5, Decimal("10.00"))

# [claude] MIL-BAL-18
def test_mil_bal_18__when_only_an_entry_of_another_workspace_exists_the_result_is_0_0_00(db, w1, w2, m1, i1, mk_entry):
    """MIL-BAL-18 — when only an entry of another workspace exists the result is (0, 0.00).
    Rules: `calculate_balance` R5, R1"""
    mk_entry(performed_at=T2, workspace_id=w2.id, qty_after=9, value_after=Decimal("99.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (0, Decimal("0.00"))

# [claude] MIL-BAL-19
def test_mil_bal_19__the_other_workspace_gets_its_own_balance(db, w2, m1, i1, mk_entry):
    """MIL-BAL-19 — the other workspace gets its own balance.
    Rules: `calculate_balance` R5"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))
    mk_entry(performed_at=T2, workspace_id=w2.id, qty_after=9, value_after=Decimal("99.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert result == (9, Decimal("99.00"))

# [claude] MIL-BAL-20
def test_mil_bal_20__an_unknown_machine_id_gives_0_0_00(db, w1, i1, mk_entry):
    """MIL-BAL-20 — an unknown machine id gives (0, 0.00).
    Rules: `calculate_balance` R1"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))

    result = dao.calculate_balance(db, machine_id=MISSING, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (0, Decimal("0.00"))

# [claude] MIL-BAL-21
def test_mil_bal_21__an_unknown_item_id_gives_0_0_00(db, w1, m1, mk_entry):
    """MIL-BAL-21 — an unknown item id gives (0, 0.00).
    Rules: `calculate_balance` R1"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == (0, Decimal("0.00"))

# [claude] MIL-BAL-22
def test_mil_bal_22__an_unknown_workspace_id_gives_0_0_00(db, m1, i1, mk_entry):
    """MIL-BAL-22 — an unknown workspace id gives (0, 0.00).
    Rules: `calculate_balance` R1"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=MISSING)

    # Then 1
    assert result == (0, Decimal("0.00"))

# [claude] MIL-BAL-23
def test_mil_bal_23__machine_id_0_gives_0_0_00(db, w1, i1, mk_entry):
    """MIL-BAL-23 — machine_id 0 gives (0, 0.00).
    Rules: `calculate_balance` R1"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))

    result = dao.calculate_balance(db, machine_id=0, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (0, Decimal("0.00"))

# [claude] MIL-BAL-24
def test_mil_bal_24__item_id_0_gives_0_0_00(db, w1, m1, mk_entry):
    """MIL-BAL-24 — item_id 0 gives (0, 0.00).
    Rules: `calculate_balance` R1"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=0, workspace_id=w1.id)

    # Then 1
    assert result == (0, Decimal("0.00"))

# [claude] MIL-BAL-25
def test_mil_bal_25__the_balance_of_a_soft_deleted_machine_is_returned(db, w1, md, i1, mk_entry):
    """MIL-BAL-25 — the balance of a soft-deleted machine is returned.
    Rules: `calculate_balance` R6"""
    e1 = mk_entry(performed_at=T1, machine_id=md.id, qty_after=4, value_after=Decimal("8.00"))
    before_e1 = snap(db, e1)

    result = dao.calculate_balance(db, machine_id=md.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (4, Decimal("8.00"))
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-BAL-26
def test_mil_bal_26__the_balance_of_a_live_machine_in_a_soft_deleted_factory_is_returned(db, w1, mf, i1, mk_entry):
    """MIL-BAL-26 — the balance of a live machine in a soft-deleted factory is returned.
    Rules: `calculate_balance` R6"""
    e1 = mk_entry(performed_at=T1, machine_id=mf.id, qty_after=4, value_after=Decimal("8.00"))
    before_e1 = snap(db, e1)

    result = dao.calculate_balance(db, machine_id=mf.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (4, Decimal("8.00"))
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-BAL-27
def test_mil_bal_27__the_balance_of_a_removed_item_is_returned(db, w1, m1, ir, mk_entry):
    """MIL-BAL-27 — the balance of a removed item is returned.
    Rules: `calculate_balance` R6"""
    e1 = mk_entry(performed_at=T1, item_id=ir.id, qty_after=4, value_after=Decimal("8.00"))
    before_e1 = snap(db, e1)

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=ir.id, workspace_id=w1.id)

    # Then 1
    assert result == (4, Decimal("8.00"))
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-BAL-28
def test_mil_bal_28__a_newer_entry_not_yet_flushed_is_not_seen(db, w1, m1, i1, mk_entry, mk_pending):
    """MIL-BAL-28 — a newer entry not yet flushed is not seen.
    Rules: `calculate_balance` R7"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))
    mk_pending(performed_at=T2, qty_after=9, value_after=Decimal("99.00"))

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (5, Decimal("10.00"))

# [claude] MIL-BAL-29
def test_mil_bal_29__the_same_newer_entry_is_seen_after_the_flush(db, w1, m1, i1, mk_entry, mk_pending):
    """MIL-BAL-29 — the same newer entry is seen after the flush.
    Rules: `calculate_balance` R7"""
    mk_entry(performed_at=T1, qty_after=5, value_after=Decimal("10.00"))
    mk_pending(performed_at=T2, qty_after=9, value_after=Decimal("99.00"))
    db.flush()

    result = dao.calculate_balance(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == (9, Decimal("99.00"))

# --------------------------------------------------------------------------- #
# `MachineItemLedgerDAO.get_latest_entry`
# --------------------------------------------------------------------------- #

# [claude] MIL-LE-01
def test_mil_le_01__with_no_entry_the_result_is_none(db, w1, m1, i1):
    """MIL-LE-01 — with no entry the result is None.
    Rules: `get_latest_entry` R1"""
    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is None

# [claude] MIL-LE-02
def test_mil_le_02__the_newest_entry_is_returned_when_it_has_the_middle_id_and_nothing_is(db, w1, m1, i1, mk_entry):
    """MIL-LE-02 — the newest entry is returned when it has the middle id, and nothing is written.
    Rules: `get_latest_entry` R2, R6, Returns"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)
    before = written(db)
    before_e2 = snap(db, e2)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, MachineItemLedger)
    # Then 2
    assert result.id == e2.id
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, e2) == before_e2

# [claude] MIL-LE-03
def test_mil_le_03__the_newest_entry_is_returned_when_it_has_the_lowest_id(db, w1, m1, i1, mk_entry):
    """MIL-LE-03 — the newest entry is returned when it has the lowest id.
    Rules: `get_latest_entry` R2"""
    e1 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id

# [claude] MIL-LE-04
def test_mil_le_04__the_newest_entry_is_returned_when_it_has_the_highest_id(db, w1, m1, i1, mk_entry):
    """MIL-LE-04 — the newest entry is returned when it has the highest id.
    Rules: `get_latest_entry` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)
    e3 = mk_entry(performed_at=T3)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e3.id

# [claude] MIL-LE-05
def test_mil_le_05__the_full_row_is_returned_with_its_prices_and_values_as_stored(db, w1, m1, i1, mk_entry):
    """MIL-LE-05 — the full row is returned with its prices and values as stored.
    Rules: `get_latest_entry` R2"""
    e1 = mk_entry(performed_at=T1, value_before=Decimal("7.00"), value_after=Decimal("10.00"), avg_price_before=Decimal("1.75"), avg_price_after=Decimal("2.00"), notes="Counted")

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.value_before == Decimal("7.00")
    assert result.value_after == Decimal("10.00")
    # Then 3
    assert result.avg_price_before == Decimal("1.75")
    assert result.avg_price_after == Decimal("2.00")
    # Then 4
    assert result.notes == "Counted"
    # Then 5
    assert result.performed_at == T1

# [claude] MIL-LE-06
def test_mil_le_06__empty_prices_and_values_come_back_as_none(db, w1, m1, i1, mk_entry):
    """MIL-LE-06 — empty prices and values come back as None.
    Rules: `get_latest_entry` R2"""
    e1 = mk_entry(performed_at=T1)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.avg_price_after is None
    # Then 3
    assert result.value_after is None

# [claude] MIL-LE-07
def test_mil_le_07__an_older_entry_with_the_highest_id_does_not_win(db, w1, m1, i1, mk_entry):
    """MIL-LE-07 — an older entry with the highest id does not win.
    Rules: `get_latest_entry` R3"""
    e1 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T1, id=HIGH_ID)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id

# [claude] MIL-LE-08
def test_mil_le_08__tied_entries_one_of_them_is_returned_never_an_older_entry(db, w1, m1, i1, mk_entry):
    """MIL-LE-08 — tied entries: one of them is returned, never an older entry.
    Rules: `get_latest_entry` R2"""
    mk_entry(performed_at=T1)
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id in [b.id, c.id, a.id]

# [claude] MIL-LE-09
@pytest.mark.xfail(strict=False, reason="BUG-664: 'Latest ledger entry' picked by timestamp alone can pick a stale row")
def test_mil_le_09__among_tied_entries_the_greatest_id_is_returned(db, w1, m1, i1, mk_entry):
    """MIL-LE-09 — among tied entries the greatest id is returned.
    Rules: `get_latest_entry` R3"""
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id in [b.id, c.id, a.id]
    # Then 2
    assert result.id == c.id

# [claude] MIL-LE-10
@pytest.mark.xfail(strict=True, reason="BUG-664: 'Latest ledger entry' picked by timestamp alone can pick a stale row")
def test_mil_le_10__the_query_asks_the_database_for_performed_at_newest_first_then_id(db, w1, m1, i1, mk_entry):
    """MIL-LE-10 — the query asks the database for performed_at newest first, then id highest first.
    Rules: `get_latest_entry` R3"""
    e1 = mk_entry(performed_at=T1)

    with StatementRecorder(db) as rec:
        result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)
    [sql] = rec.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_item_ledger.performed_at DESC" in order_part
    # Then 4
    assert "machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part

# [claude] MIL-LE-11
def test_mil_le_11__a_newer_entry_of_another_machine_is_not_considered(db, w1, m1, m2, i1, mk_entry):
    """MIL-LE-11 — a newer entry of another machine is not considered.
    Rules: `get_latest_entry` R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, machine_id=m2.id)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id

# [claude] MIL-LE-12
def test_mil_le_12__when_only_an_entry_of_another_machine_exists_the_result_is_none(db, w1, m1, m2, i1, mk_entry):
    """MIL-LE-12 — when only an entry of another machine exists the result is None.
    Rules: `get_latest_entry` R4"""
    mk_entry(performed_at=T2, machine_id=m2.id)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is None

# [claude] MIL-LE-13
def test_mil_le_13__a_newer_entry_of_another_item_is_not_considered(db, w1, m1, i1, i2, mk_entry):
    """MIL-LE-13 — a newer entry of another item is not considered.
    Rules: `get_latest_entry` R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, item_id=i2.id)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id

# [claude] MIL-LE-14
def test_mil_le_14__when_only_an_entry_of_another_item_exists_the_result_is_none(db, w1, m1, i1, i2, mk_entry):
    """MIL-LE-14 — when only an entry of another item exists the result is None.
    Rules: `get_latest_entry` R4"""
    mk_entry(performed_at=T2, item_id=i2.id)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is None

# [claude] MIL-LE-15
def test_mil_le_15__a_newer_entry_of_another_workspace_is_not_considered(db, w1, w2, m1, i1, mk_entry):
    """MIL-LE-15 — a newer entry of another workspace is not considered.
    Rules: `get_latest_entry` R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, workspace_id=w2.id)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id

# [claude] MIL-LE-16
def test_mil_le_16__when_only_an_entry_of_another_workspace_exists_the_result_is_none(db, w1, w2, m1, i1, mk_entry):
    """MIL-LE-16 — when only an entry of another workspace exists the result is None.
    Rules: `get_latest_entry` R4"""
    mk_entry(performed_at=T2, workspace_id=w2.id)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is None

# [claude] MIL-LE-17
def test_mil_le_17__the_other_workspace_gets_its_own_entry(db, w2, m1, i1, mk_entry):
    """MIL-LE-17 — the other workspace gets its own entry.
    Rules: `get_latest_entry` R4"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, workspace_id=w2.id)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert result.id == e2.id

# [claude] MIL-LE-18
def test_mil_le_18__an_unknown_machine_id_gives_none(db, w1, i1, mk_entry):
    """MIL-LE-18 — an unknown machine id gives None.
    Rules: `get_latest_entry` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_latest_entry(db, machine_id=MISSING, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is None

# [claude] MIL-LE-19
def test_mil_le_19__an_unknown_item_id_gives_none(db, w1, m1, mk_entry):
    """MIL-LE-19 — an unknown item id gives None.
    Rules: `get_latest_entry` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None

# [claude] MIL-LE-20
def test_mil_le_20__an_unknown_workspace_id_gives_none(db, m1, i1, mk_entry):
    """MIL-LE-20 — an unknown workspace id gives None.
    Rules: `get_latest_entry` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=MISSING)

    # Then 1
    assert result is None

# [claude] MIL-LE-21
def test_mil_le_21__the_latest_entry_of_a_soft_deleted_machine_is_returned(db, w1, md, i1, mk_entry):
    """MIL-LE-21 — the latest entry of a soft-deleted machine is returned.
    Rules: `get_latest_entry` R5"""
    e1 = mk_entry(performed_at=T1, machine_id=md.id)
    before_e1 = snap(db, e1)

    result = dao.get_latest_entry(db, machine_id=md.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-LE-22
def test_mil_le_22__the_latest_entry_of_a_live_machine_in_a_soft_deleted_factory_is_returned(db, w1, mf, i1, mk_entry):
    """MIL-LE-22 — the latest entry of a live machine in a soft-deleted factory is returned.
    Rules: `get_latest_entry` R5"""
    e1 = mk_entry(performed_at=T1, machine_id=mf.id)
    before_e1 = snap(db, e1)

    result = dao.get_latest_entry(db, machine_id=mf.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-LE-23
def test_mil_le_23__the_latest_entry_of_a_removed_item_is_returned(db, w1, m1, ir, mk_entry):
    """MIL-LE-23 — the latest entry of a removed item is returned.
    Rules: `get_latest_entry` R5"""
    e1 = mk_entry(performed_at=T1, item_id=ir.id)
    before_e1 = snap(db, e1)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=ir.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert snap(db, e1) == before_e1


# [claude] MIL-LE-24
def test_mil_le_24__a_pending_entry_stays_pending_and_is_not_seen_the_call_writes_nothing(db, w1, m1, i1, mk_entry, mk_pending):
    """MIL-LE-24 — a pending entry stays pending and is not seen: the call writes nothing.
    Rules: `get_latest_entry` R6"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_pending(performed_at=T2)

    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert e2 in db.new


# [claude] MIL-LE-25
def test_mil_le_25__the_lookup_never_commits(db, w1, m1, i1, mk_entry, commit_spy):
    """MIL-LE-25 — the lookup never commits.
    Rules: `get_latest_entry` R6"""
    e1 = mk_entry(performed_at=T1)

    sp = db.begin_nested()
    result = dao.get_latest_entry(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id
    # Then 2
    sp.rollback()
    row = reread(db, e1)
    assert row.performed_at == T1
    # Then 3
    assert commit_spy.call_count == 0

# --------------------------------------------------------------------------- #
# `MachineItemLedgerDAO.get_by_performer`
# --------------------------------------------------------------------------- #

# [claude] MIL-PF-01
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_01__entries_of_every_machine_item_and_transaction_type_of_that_user_are(db, w1, u1, m2, i2, mk_entry):
    """MIL-PF-01 — entries of every machine, item and transaction type of that user are returned.
    Rules: `get_by_performer` R1"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2, machine_id=m2.id)
    e3 = mk_entry(performed_at=T3, item_id=i2.id)
    e4 = mk_entry(performed_at=T4, transaction_type="consumption")

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e4.id, e3.id, e2.id, e1.id]

# [claude] MIL-PF-02
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_02__an_entry_of_another_performer_is_not_returned(db, w1, u1, u2, mk_entry):
    """MIL-PF-02 — an entry of another performer is not returned.
    Rules: `get_by_performer` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2, performed_by=u2.id)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-PF-03
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_03__the_same_user_s_entry_in_another_workspace_is_not_returned(db, w1, w2, u1, mk_entry):
    """MIL-PF-03 — the same user's entry in another workspace is not returned.
    Rules: `get_by_performer` R1"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-PF-04
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_04__the_other_workspace_gets_only_its_own_entry(db, w2, u1, mk_entry):
    """MIL-PF-04 — the other workspace gets only its own entry.
    Rules: `get_by_performer` R1"""
    mk_entry(performed_at=T1)
    x9 = mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x9.id]

# [claude] MIL-PF-05
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_05__an_unknown_profile_id_returns_an_empty_list(db, w1, mk_entry):
    """MIL-PF-05 — an unknown profile id returns an empty list.
    Rules: `get_by_performer` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_performer(db, performed_by=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-PF-06
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_06__profile_id_0_returns_an_empty_list(db, w1, mk_entry):
    """MIL-PF-06 — profile id 0 returns an empty list.
    Rules: `get_by_performer` R1"""
    mk_entry(performed_at=T1)

    result = dao.get_by_performer(db, performed_by=0, workspace_id=w1.id)

    # Then 1
    assert result == []

# [claude] MIL-PF-07
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_07__returns_a_list_of_ledger_rows_newest_first_whatever_the_insertion_order(db, w1, u1, mk_entry):
    """MIL-PF-07 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing.
    Rules: `get_by_performer` R2, R1"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert isinstance(result[0], MachineItemLedger)
    # Then 3
    assert ids(result) == [e2.id, e3.id, e1.id]
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-PF-08
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_08__skip_1_and_limit_1_return_exactly_the_middle_entry(db, w1, u1, mk_entry):
    """MIL-PF-08 — skip 1 and limit 1 return exactly the middle entry.
    Rules: `get_by_performer` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e3.id]

# [claude] MIL-PF-09
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_09__limit_2_returns_the_two_newest_entries(db, w1, u1, mk_entry):
    """MIL-PF-09 — limit 2 returns the two newest entries.
    Rules: `get_by_performer` R2"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    e3 = mk_entry(performed_at=T2)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert ids(result) == [e2.id, e3.id]

# [claude] MIL-PF-10
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_10__limit_1_returns_only_the_newest_entry(db, w1, u1, mk_entry):
    """MIL-PF-10 — limit 1 returns only the newest entry.
    Rules: `get_by_performer` R2"""
    mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert ids(result) == [e2.id]

# [claude] MIL-PF-11
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_11__skip_one_below_the_number_of_entries_returns_the_oldest_entry(db, w1, u1, mk_entry):
    """MIL-PF-11 — skip one below the number of entries returns the oldest entry.
    Rules: `get_by_performer` R2"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-PF-12
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_12__skip_equal_to_the_number_of_entries_returns_an_empty_list(db, w1, u1, mk_entry):
    """MIL-PF-12 — skip equal to the number of entries returns an empty list.
    Rules: `get_by_performer` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []

# [claude] MIL-PF-13
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_13__skip_past_the_number_of_entries_returns_an_empty_list(db, w1, u1, mk_entry):
    """MIL-PF-13 — skip past the number of entries returns an empty list.
    Rules: `get_by_performer` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, skip=4)

    # Then 1
    assert result == []

# [claude] MIL-PF-14
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_14__limit_0_returns_an_empty_list(db, w1, u1, mk_entry):
    """MIL-PF-14 — limit 0 returns an empty list.
    Rules: `get_by_performer` R2"""
    mk_entry(performed_at=T1)
    mk_entry(performed_at=T3)
    mk_entry(performed_at=T2)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []

# [claude] MIL-PF-15
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_15__paging_counts_matching_entries_only_newer_entries_left_out_by_the(db, w1, w2, u1, u2, mk_entry):
    """MIL-PF-15 — paging counts matching entries only: newer entries left out by the filters use no place on the page.
    Rules: `get_by_performer` R2"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T2)
    mk_entry(performed_at=T3, performed_by=u2.id)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert ids(result) == [e1.id]

# [claude] MIL-PF-16
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_16__by_default_at_most_the_100_newest_of_101_entries_are_returned_the(db, w1, u1, mk_entry):
    """MIL-PF-16 — by default at most the 100 newest of 101 entries are returned; the oldest is missing.
    Rules: `get_by_performer` R2"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 1, -1)]
    # Then 3
    assert n[1].id not in ids(result)

# [claude] MIL-PF-17
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_17__exactly_100_entries_are_all_returned_by_default(db, w1, u1, mk_entry):
    """MIL-PF-17 — exactly 100 entries are all returned by default.
    Rules: `get_by_performer` R2"""
    n = mk_n(mk_entry, 100)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert ids(result) == [n[k].id for k in range(100, 0, -1)]

# [claude] MIL-PF-18
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_18__limit_101_returns_all_101_entries_the_method_has_no_upper_cap(db, w1, u1, mk_entry):
    """MIL-PF-18 — limit 101 returns all 101 entries: the method has no upper cap.
    Rules: `get_by_performer` R2"""
    n = mk_n(mk_entry, 101)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert ids(result) == [n[k].id for k in range(101, 0, -1)]

# [claude] MIL-PF-19
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_19__a_negative_limit_makes_the_database_reject_the_query(db, w1, u1, mk_entry):
    """MIL-PF-19 — a negative limit makes the database reject the query.
    Rules: `get_by_performer` R2, Errors (as get_by_item)"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-PF-20
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_20__a_negative_skip_makes_the_database_reject_the_query(db, w1, u1, mk_entry):
    """MIL-PF-20 — a negative skip makes the database reject the query.
    Rules: `get_by_performer` R2, Errors (as get_by_item)"""
    mk_entry(performed_at=T1)
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id, skip=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201X"
    # Then 4
    assert "OFFSET must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-PF-21
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_21__entries_with_the_same_performed_at_come_back_by_id_highest_first(db, w1, u1, mk_entry):
    """MIL-PF-21 — entries with the same performed_at come back by id, highest first.
    Rules: `get_by_performer` R2"""
    b = mk_entry(performed_at=T2, qty_after=15, value_after=Decimal("150.00"))
    c = mk_entry(performed_at=T2, id=HIGH_ID, qty_after=10, value_after=Decimal("100.00"))
    a = mk_entry(performed_at=T2, qty_after=99, value_after=Decimal("990.00"))

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [c.id, a.id, b.id]

# [claude] MIL-PF-22
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_22__the_query_asks_the_database_for_performed_at_newest_first_then_id(db, w1, u1, mk_entry):
    """MIL-PF-22 — the query asks the database for performed_at newest first, then id highest first.
    Rules: `get_by_performer` R2"""
    e1 = mk_entry(performed_at=T1)

    with StatementRecorder(db) as rec:
        result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)
    [sql] = rec.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_item_ledger.performed_at DESC" in order_part
    # Then 4
    assert "machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part

# [claude] MIL-PF-23
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_23__an_entry_of_a_soft_deleted_machine_is_returned(db, w1, u1, md, mk_entry):
    """MIL-PF-23 — an entry of a soft-deleted machine is returned.
    Rules: `get_by_performer` R3"""
    e1 = mk_entry(performed_at=T1, machine_id=md.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-PF-24
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_24__an_entry_of_a_live_machine_in_a_soft_deleted_factory_is_returned(db, w1, u1, mf, mk_entry):
    """MIL-PF-24 — an entry of a live machine in a soft-deleted factory is returned.
    Rules: `get_by_performer` R3"""
    e1 = mk_entry(performed_at=T1, machine_id=mf.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-PF-25
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_25__an_entry_of_a_removed_item_is_returned(db, w1, u1, ir, mk_entry):
    """MIL-PF-25 — an entry of a removed item is returned.
    Rules: `get_by_performer` R3"""
    e1 = mk_entry(performed_at=T1, item_id=ir.id)
    before_e1 = snap(db, e1)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert snap(db, e1) == before_e1

# [claude] MIL-PF-26
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_26__the_call_writes_nothing(db, w1, u1, mk_entry):
    """MIL-PF-26 — the call writes nothing.
    Rules: `get_by_performer` R3"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2)
    before = written(db)
    before_e1 = snap(db, e1)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e2.id, e1.id]
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, e1) == before_e1

# [claude] MIL-PF-27
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_27__performed_by_none_returns_an_empty_list_and_raises_nothing(db, w1, mk_entry):
    """MIL-PF-27 — performed_by None returns an empty list and raises nothing.
    Rules: `get_by_performer` R4"""
    mk_entry(performed_at=T1)

    result = dao.get_by_performer(db, performed_by=None, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIL-PF-28
@pytest.mark.xfail(strict=True, reason="BUG-645: User transaction report always crashes")
def test_mil_pf_28__a_pending_entry_stays_pending_and_is_not_seen_the_call_writes_nothing(db, w1, u1, mk_entry, mk_pending):
    """MIL-PF-28 — a pending entry stays pending and is not seen: the call writes nothing.
    Rules: `get_by_performer` R3"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_pending(performed_at=T2)

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert e2 in db.new

# --------------------------------------------------------------------------- #
# Inherited `BaseDAO` methods on `MachineItemLedger`
# --------------------------------------------------------------------------- #

# [claude] MIL-INH-01
def test_mil_inh_01__create_with_a_dict_saves_the_row_with_the_required_columns_as_given(db, full, w1, u1, m1, i1):
    """MIL-INH-01 — create with a dict saves the row with the required columns as given.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in=full)

    # Then 1
    assert result.id is not None
    # Then 2
    assert isinstance(result, MachineItemLedger)
    # Then 3
    assert count_rows(db, workspace_id=w1.id) == 1
    # Then 4
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    assert row.performed_by == u1.id
    # Then 5
    row = reread(db, result)
    assert row.transaction_type == "manual_add"
    assert row.source_type == "manual"
    # Then 6
    row = reread(db, result)
    assert row.quantity == 3
    assert row.qty_before == 4
    assert row.qty_after == 7
    # Then 7
    row = reread(db, result)
    assert row.unit_cost == Decimal("2.50")
    assert row.total_cost == Decimal("7.50")

# [claude] MIL-INH-02
def test_mil_inh_02__create_leaves_every_nullable_column_empty(db, full):
    """MIL-INH-02 — create leaves every nullable column empty.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in=full)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.value_before is None
    assert row.value_after is None
    assert row.avg_price_before is None
    assert row.avg_price_after is None
    # Then 3
    row = reread(db, result)
    assert row.source_id is None
    assert row.order_id is None
    assert row.order_type is None
    assert row.invoice_id is None
    assert row.notes is None
    # Then 4
    row = reread(db, result)
    assert row.transfer_source_id is None
    assert row.transfer_source_type is None
    assert row.transfer_destination_id is None
    assert row.transfer_destination_type is None

# [claude] MIL-INH-03
def test_mil_inh_03__create_fills_performed_at_with_a_naive_utc_time_at_flush(db, full):
    """MIL-INH-03 — create fills performed_at with a naive UTC time at flush.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in=full)

    # Then 1
    assert result.performed_at is not None
    # Then 2
    row = reread(db, result)
    assert row.performed_at.tzinfo is None
    # Then 3
    row = reread(db, result)
    assert abs(datetime.now(timezone.utc).replace(tzinfo=None) - row.performed_at) < timedelta(minutes=5)

# [claude] MIL-INH-04
def test_mil_inh_04__create_computes_nothing_inconsistent_figures_are_stored_as_given(db, full):
    """MIL-INH-04 — create computes nothing: inconsistent figures are stored as given.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in={**full, "total_cost": Decimal("999.00"), "qty_after": 50, "value_after": Decimal("1.00"), "avg_price_after": Decimal("3.00")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.total_cost == Decimal("999.00")
    assert row.qty_after == 50
    # Then 3
    row = reread(db, result)
    assert row.value_after == Decimal("1.00")
    assert row.avg_price_after == Decimal("3.00")

# [claude] MIL-INH-05
def test_mil_inh_05__create_stores_the_optional_columns_given(db, full):
    """MIL-INH-05 — create stores the optional columns given.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in={**full, "source_id": 77, "notes": "From the count", "value_before": Decimal("8.00"), "avg_price_before": Decimal("2.00")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.source_id == 77
    assert row.notes == "From the count"
    # Then 3
    row = reread(db, result)
    assert row.value_before == Decimal("8.00")
    assert row.avg_price_before == Decimal("2.00")

# [claude] MIL-INH-06
def test_mil_inh_06__create_is_flushed_not_committed_a_rollback_removes_the_row(db, full, w1, commit_spy):
    """MIL-INH-06 — create is flushed, not committed: a rollback removes the row.
    Rules: `inherited` R1"""
    sp = db.begin_nested()
    result = dao.create(db, obj_in=full)

    # Then 1
    assert result.id is not None
    # Then 2
    assert count_rows(db, workspace_id=w1.id) == 1
    # Then 3
    sp.rollback()
    assert count_rows(db, workspace_id=w1.id) == 0
    # Then 4
    assert commit_spy.call_count == 0

# [claude] MIL-INH-07
def test_mil_inh_07__create_with_machineitemledgercreate_fails_on_flush_and_saves_nothing(db, m1, i1):
    """MIL-INH-07 — create with MachineItemLedgerCreate fails on flush and saves nothing.
    Rules: `inherited` R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=MachineItemLedgerCreate(machine_id=m1.id, item_id=i1.id, transaction_type="manual_add", quantity=3, unit_cost=Decimal("2.50"), total_cost=Decimal("7.50"), qty_before=4, qty_after=7, source_type="manual"))

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "workspace_id"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-08
def test_mil_inh_08__an_unknown_workspace_id_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-08 — an unknown workspace_id fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 2"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "workspace_id": MISSING})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_item_ledger_workspace_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-09
def test_mil_inh_09__an_unknown_machine_id_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-09 — an unknown machine_id fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 2"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "machine_id": MISSING})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_item_ledger_machine_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-10
def test_mil_inh_10__an_unknown_item_id_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-10 — an unknown item_id fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 2"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "item_id": MISSING})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_item_ledger_item_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-11
def test_mil_inh_11__an_unknown_performed_by_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-11 — an unknown performed_by fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 2"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "performed_by": MISSING})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_item_ledger_performed_by_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-12
def test_mil_inh_12__an_unknown_invoice_id_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-12 — an unknown invoice_id fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 2"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "invoice_id": MISSING})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_item_ledger_invoice_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-13
def test_mil_inh_13__performed_by_none_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-13 — performed_by None fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "performed_by": None})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "performed_by"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-14
def test_mil_inh_14__a_missing_workspace_id_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-14 — a missing workspace_id fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={k: v for k, v in full.items() if k != "workspace_id"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "workspace_id"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-15
def test_mil_inh_15__a_missing_machine_id_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-15 — a missing machine_id fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={k: v for k, v in full.items() if k != "machine_id"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "machine_id"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-16
def test_mil_inh_16__a_missing_item_id_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-16 — a missing item_id fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={k: v for k, v in full.items() if k != "item_id"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "item_id"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-17
def test_mil_inh_17__a_missing_transaction_type_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-17 — a missing transaction_type fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={k: v for k, v in full.items() if k != "transaction_type"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "transaction_type"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-18
def test_mil_inh_18__a_missing_quantity_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-18 — a missing quantity fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={k: v for k, v in full.items() if k != "quantity"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "quantity"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-19
def test_mil_inh_19__a_missing_qty_before_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-19 — a missing qty_before fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={k: v for k, v in full.items() if k != "qty_before"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "qty_before"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-20
def test_mil_inh_20__a_missing_qty_after_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-20 — a missing qty_after fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={k: v for k, v in full.items() if k != "qty_after"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "qty_after"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-21
def test_mil_inh_21__a_missing_unit_cost_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-21 — a missing unit_cost fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={k: v for k, v in full.items() if k != "unit_cost"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "unit_cost"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-22
def test_mil_inh_22__a_missing_total_cost_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-22 — a missing total_cost fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={k: v for k, v in full.items() if k != "total_cost"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "total_cost"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-23
def test_mil_inh_23__a_missing_source_type_fails_on_flush_and_saves_nothing(db, full):
    """MIL-INH-23 — a missing source_type fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={k: v for k, v in full.items() if k != "source_type"})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "source_type"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-24
def test_mil_inh_24__any_string_is_saved_as_transaction_type(db, full):
    """MIL-INH-24 — any string is saved as transaction_type.
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**full, "transaction_type": "not a real type"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.transaction_type == "not a real type"

# [claude] MIL-INH-25
def test_mil_inh_25__a_negative_quantity_is_saved(db, full):
    """MIL-INH-25 — a negative quantity is saved.
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**full, "quantity": -5})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.quantity == -5

# [claude] MIL-INH-26
def test_mil_inh_26__a_negative_unit_cost_and_total_cost_are_saved(db, full):
    """MIL-INH-26 — a negative unit_cost and total_cost are saved.
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("-2.50"), "total_cost": Decimal("-7.50")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("-2.50")
    assert row.total_cost == Decimal("-7.50")

# [claude] MIL-INH-27
def test_mil_inh_27__machine_and_item_need_not_belong_to_the_entry_s_workspace(db, full, w2, m1, i1):
    """MIL-INH-27 — machine and item need not belong to the entry's workspace.
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**full, "workspace_id": w2.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.machine_id == m1.id
    assert row.item_id == i1.id

# [claude] MIL-INH-28
def test_mil_inh_28__every_text_column_accepts_a_value_of_exactly_its_limit(db, full):
    """MIL-INH-28 — every text column accepts a value of exactly its limit.
    Rules: `inherited` R4"""
    result = dao.create(db, obj_in={**full, "transaction_type": "t" * 50, "source_type": "s" * 50, "order_type": "o" * 30, "transfer_source_type": "a" * 50, "transfer_destination_type": "b" * 50})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.transaction_type == "t" * 50
    assert row.source_type == "s" * 50
    assert row.order_type == "o" * 30
    # Then 3
    row = reread(db, result)
    assert row.transfer_source_type == "a" * 50
    assert row.transfer_destination_type == "b" * 50

# [claude] MIL-INH-29
def test_mil_inh_29__a_transaction_type_of_51_characters_is_too_long_and_nothing_is_saved(db, full):
    """MIL-INH-29 — a transaction_type of 51 characters is too long and nothing is saved.
    Rules: `inherited` R4"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "transaction_type": "t" * 51})

    # Then 2
    assert isinstance(exc.value.orig, StringDataRightTruncation)
    # Then 3
    assert exc.value.orig.pgcode == "22001"
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-30
def test_mil_inh_30__a_source_type_of_51_characters_is_too_long_and_nothing_is_saved(db, full):
    """MIL-INH-30 — a source_type of 51 characters is too long and nothing is saved.
    Rules: `inherited` R4"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "source_type": "s" * 51})

    # Then 2
    assert isinstance(exc.value.orig, StringDataRightTruncation)
    # Then 3
    assert exc.value.orig.pgcode == "22001"
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-31
def test_mil_inh_31__a_order_type_of_31_characters_is_too_long_and_nothing_is_saved(db, full):
    """MIL-INH-31 — a order_type of 31 characters is too long and nothing is saved.
    Rules: `inherited` R4"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "order_type": "o" * 31})

    # Then 2
    assert isinstance(exc.value.orig, StringDataRightTruncation)
    # Then 3
    assert exc.value.orig.pgcode == "22001"
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-32
def test_mil_inh_32__a_transfer_source_type_of_51_characters_is_too_long_and_nothing_is_saved(db, full):
    """MIL-INH-32 — a transfer_source_type of 51 characters is too long and nothing is saved.
    Rules: `inherited` R4"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "transfer_source_type": "a" * 51})

    # Then 2
    assert isinstance(exc.value.orig, StringDataRightTruncation)
    # Then 3
    assert exc.value.orig.pgcode == "22001"
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-33
def test_mil_inh_33__a_transfer_destination_type_of_51_characters_is_too_long_and_nothing_is(db, full):
    """MIL-INH-33 — a transfer_destination_type of 51 characters is too long and nothing is saved.
    Rules: `inherited` R4"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "transfer_destination_type": "b" * 51})

    # Then 2
    assert isinstance(exc.value.orig, StringDataRightTruncation)
    # Then 3
    assert exc.value.orig.pgcode == "22001"
    # Then 4
    assert written(db) == before

# [claude] MIL-INH-34
def test_mil_inh_34__the_greatest_amount_a_cost_column_holds_is_saved(db, full):
    """MIL-INH-34 — the greatest amount a cost column holds is saved.
    Rules: `inherited` R1b"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("9999999999999.99")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("9999999999999.99")

# [claude] MIL-INH-35
def test_mil_inh_35__an_amount_with_one_more_digit_is_too_big_and_nothing_is_saved(db, full):
    """MIL-INH-35 — an amount with one more digit is too big and nothing is saved.
    Rules: `inherited` R1b, Errors row 5"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "unit_cost": Decimal("10000000000000.00")})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "numeric field overflow" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-INH-36
def test_mil_inh_36__hard_deleting_a_machine_that_has_entries_fails_and_changes_nothing(db, m2, mk_entry):
    """MIL-INH-36 — hard-deleting a machine that has entries fails and changes nothing.
    Rules: `inherited` R5, Errors row 3"""
    e1 = mk_entry(performed_at=T1, machine_id=m2.id)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.execute(text("delete from machines where id = :i"), {"i": m2.id})

    # Then 2
    assert isinstance(exc.value.orig, RestrictViolation)
    # Then 3
    assert "machine_item_ledger_machine_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-INH-37
def test_mil_inh_37__hard_deleting_an_item_that_has_entries_fails_and_changes_nothing(db, i2, mk_entry):
    """MIL-INH-37 — hard-deleting an item that has entries fails and changes nothing.
    Rules: `inherited` R5, Errors row 3"""
    e1 = mk_entry(performed_at=T1, item_id=i2.id)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.execute(text("delete from items where id = :i"), {"i": i2.id})

    # Then 2
    assert isinstance(exc.value.orig, RestrictViolation)
    # Then 3
    assert "machine_item_ledger_item_id_fkey" in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-INH-38
def test_mil_inh_38__hard_deleting_a_profile_that_has_entries_fails_on_the_not_null_column(db, u2, mk_entry):
    """MIL-INH-38 — hard-deleting a profile that has entries fails on the NOT NULL column and changes nothing.
    Rules: `inherited` R5, Errors row 4"""
    e1 = mk_entry(performed_at=T1, performed_by=u2.id)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.execute(text("delete from profiles where id = :i"), {"i": u2.id})

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "performed_by"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-INH-39
def test_mil_inh_39__get_by_workspace_returns_the_workspace_s_entries_and_none_of_another(db, w1, w2, mk_entry):
    """MIL-INH-39 — get_by_workspace returns the workspace's entries and none of another workspace.
    Rules: `inherited` R6, R8"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == sorted([e1.id, e2.id])
    # Then 2
    assert len(result) == 2

# [claude] MIL-INH-40
def test_mil_inh_40__get_by_workspace_applies_skip_and_limit_to_the_workspace_s_entries(db, w1, w2, mk_entry):
    """MIL-INH-40 — get_by_workspace applies skip and limit to the workspace's entries.
    Rules: `inherited` R6"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2)
    e3 = mk_entry(performed_at=T3)
    mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert result[0].id in [e1.id, e2.id, e3.id]

# [claude] MIL-INH-41
@pytest.mark.xfail(strict=False, reason="BUG-100: BaseDAO list methods have no sort order")
def test_mil_inh_41__get_by_workspace_returns_the_entries_by_id_lowest_first(db, w1, mk_entry):
    """MIL-INH-41 — get_by_workspace returns the entries by id, lowest first.
    Rules: `inherited` R6"""
    b = mk_entry(performed_at=T1)
    c = mk_entry(performed_at=T2, id=HIGH_ID)
    a = mk_entry(performed_at=T3)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == sorted([b.id, c.id, a.id])
    # Then 2
    assert ids(result) == [b.id, a.id, c.id]

# [claude] MIL-INH-42
@pytest.mark.xfail(strict=True, reason="BUG-100: BaseDAO list methods have no sort order")
def test_mil_inh_42__the_workspace_list_query_asks_the_database_for_id_lowest_first(db, w1, mk_entry):
    """MIL-INH-42 — the workspace list query asks the database for id, lowest first.
    Rules: `inherited` R6"""
    e1 = mk_entry(performed_at=T1)

    with StatementRecorder(db) as rec:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    [sql] = rec.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [e1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_item_ledger.id" in order_part
    # Then 4
    assert "machine_item_ledger.id DESC" not in order_part

# [claude] MIL-INH-43
def test_mil_inh_43__update_with_a_dict_changes_the_column_given_and_only_that(db, mk_entry):
    """MIL-INH-43 — update with a dict changes the column given and only that.
    Rules: `inherited` R7"""
    e1 = mk_entry(performed_at=T1, qty_after=5, notes="Keep")

    result = dao.update(db, db_obj=e1, obj_in={"qty_after": 99})

    # Then 1
    assert result is e1
    # Then 2
    row = reread(db, e1)
    assert row.qty_after == 99
    # Then 3
    row = reread(db, e1)
    assert row.notes == "Keep"
    assert row.quantity == 1
    assert row.qty_before == 4
    # Then 4
    row = reread(db, e1)
    assert row.performed_at == T1

# [claude] MIL-INH-44
def test_mil_inh_44__update_with_machineitemledgerupdate_changes_notes_and_only_that(db, mk_entry):
    """MIL-INH-44 — update with MachineItemLedgerUpdate changes notes and only that.
    Rules: `inherited` R7"""
    e1 = mk_entry(performed_at=T1, qty_after=5)

    result = dao.update(db, db_obj=e1, obj_in=MachineItemLedgerUpdate(notes="Counted again"))

    # Then 1
    assert result is e1
    # Then 2
    row = reread(db, e1)
    assert row.notes == "Counted again"
    # Then 3
    row = reread(db, e1)
    assert row.qty_after == 5
    assert row.quantity == 1
    # Then 4
    row = reread(db, e1)
    assert row.performed_at == T1

# [claude] MIL-INH-45
def test_mil_inh_45__update_is_flushed_not_committed_a_rollback_restores_the_old_value(db, mk_entry, commit_spy):
    """MIL-INH-45 — update is flushed, not committed: a rollback restores the old value.
    Rules: `inherited` R7"""
    e1 = mk_entry(performed_at=T1, qty_after=5)

    sp = db.begin_nested()
    result = dao.update(db, db_obj=e1, obj_in={"qty_after": 99})

    # Then 1
    assert result is e1
    # Then 2
    assert db.scalar(select(MachineItemLedger.qty_after).where(MachineItemLedger.id == e1.id)) == 99
    # Then 3
    sp.rollback()
    row = reread(db, e1)
    assert row.qty_after == 5
    # Then 4
    assert commit_spy.call_count == 0

# [claude] MIL-INH-46
def test_mil_inh_46__remove_hard_deletes_the_entry_and_leaves_the_others(db, mk_entry):
    """MIL-INH-46 — remove hard-deletes the entry and leaves the others.
    Rules: `inherited` R7"""
    e1 = mk_entry(performed_at=T1)
    e2 = mk_entry(performed_at=T2)
    e1_id = e1.id
    before_e2 = snap(db, e2)

    result = dao.remove(db, id=e1_id)

    # Then 1
    assert result.id == e1_id
    # Then 2
    assert count_rows(db, id=e1_id) == 0
    # Then 3
    assert snap(db, e2) == before_e2

# [claude] MIL-INH-47
def test_mil_inh_47__remove_is_flushed_not_committed_a_rollback_restores_the_entry(db, mk_entry, commit_spy):
    """MIL-INH-47 — remove is flushed, not committed: a rollback restores the entry.
    Rules: `inherited` R7"""
    e1 = mk_entry(performed_at=T1)
    e1_id = e1.id

    sp = db.begin_nested()
    result = dao.remove(db, id=e1_id)

    # Then 1
    assert result.id == e1_id
    # Then 2
    assert count_rows(db, id=e1_id) == 0
    # Then 3
    sp.rollback()
    assert count_rows(db, id=e1_id) == 1
    # Then 4
    assert commit_spy.call_count == 0

# [claude] MIL-INH-48
def test_mil_inh_48__get_returns_an_entry_of_any_workspace(db, w2, mk_entry):
    """MIL-INH-48 — get returns an entry of any workspace.
    Rules: `inherited` R8"""
    x9 = mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get(db, x9.id)

    # Then 1
    assert result.id == x9.id
    # Then 2
    assert result.workspace_id == w2.id

# [claude] MIL-INH-49
def test_mil_inh_49__get_by_id_and_workspace_returns_an_entry_of_that_workspace(db, w1, mk_entry):
    """MIL-INH-49 — get_by_id_and_workspace returns an entry of that workspace.
    Rules: `inherited` R8"""
    e1 = mk_entry(performed_at=T1)

    result = dao.get_by_id_and_workspace(db, id=e1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == e1.id

# [claude] MIL-INH-50
def test_mil_inh_50__get_by_id_and_workspace_returns_none_for_an_entry_of_another_workspace(db, w1, w2, mk_entry):
    """MIL-INH-50 — get_by_id_and_workspace returns None for an entry of another workspace.
    Rules: `inherited` R8"""
    x9 = mk_entry(performed_at=T5, workspace_id=w2.id)

    result = dao.get_by_id_and_workspace(db, id=x9.id, workspace_id=w1.id)

    # Then 1
    assert result is None

# [claude] MIL-INH-51
def test_mil_inh_51__a_unit_cost_of_1_005_is_stored_as_1_01_a_fresh_read_shows_the_rounded(db, full):
    """MIL-INH-51 — a unit_cost of 1.005 is stored as 1.01: a fresh read shows the rounded value.
    Rules: `inherited` R1a"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("1.005")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("1.01")

# [claude] MIL-INH-52
def test_mil_inh_52__a_unit_cost_of_1_004_is_stored_as_1_00_a_fresh_read_shows_the_rounded(db, full):
    """MIL-INH-52 — a unit_cost of 1.004 is stored as 1.00: a fresh read shows the rounded value.
    Rules: `inherited` R1a"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("1.004")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("1.00")

# [claude] MIL-INH-53
def test_mil_inh_53__a_unit_cost_of_1_015_is_stored_as_1_02_a_fresh_read_shows_the_rounded(db, full):
    """MIL-INH-53 — a unit_cost of 1.015 is stored as 1.02: a fresh read shows the rounded value.
    Rules: `inherited` R1a"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("1.015")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("1.02")

# [claude] MIL-INH-54
def test_mil_inh_54__a_unit_cost_of_1_025_is_stored_as_1_03_a_fresh_read_shows_the_rounded(db, full):
    """MIL-INH-54 — a unit_cost of 1.025 is stored as 1.03: a fresh read shows the rounded value.
    Rules: `inherited` R1a"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("1.025")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("1.03")

# [claude] MIL-INH-55
def test_mil_inh_55__a_unit_cost_of_2_675_is_stored_as_2_68_a_fresh_read_shows_the_rounded(db, full):
    """MIL-INH-55 — a unit_cost of 2.675 is stored as 2.68: a fresh read shows the rounded value.
    Rules: `inherited` R1a"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("2.675")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("2.68")

# [claude] MIL-INH-56
def test_mil_inh_56__a_unit_cost_of_0_125_is_stored_as_0_13_a_fresh_read_shows_the_rounded(db, full):
    """MIL-INH-56 — a unit_cost of 0.125 is stored as 0.13: a fresh read shows the rounded value.
    Rules: `inherited` R1a"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("0.125")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("0.13")

# [claude] MIL-INH-57
def test_mil_inh_57__a_unit_cost_of_0_0049_is_stored_as_0_00_a_fresh_read_shows_the_rounded(db, full):
    """MIL-INH-57 — a unit_cost of 0.0049 is stored as 0.00: a fresh read shows the rounded value.
    Rules: `inherited` R1a"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("0.0049")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("0.00")

# [claude] MIL-INH-58
def test_mil_inh_58__a_unit_cost_of_1_005_is_stored_as_1_01_a_fresh_read_shows_the_rounded(db, full):
    """MIL-INH-58 — a unit_cost of -1.005 is stored as -1.01: a fresh read shows the rounded value.
    Rules: `inherited` R1a"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("-1.005")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("-1.01")

# [claude] MIL-INH-59
def test_mil_inh_59__a_python_float_1_005_is_stored_as_1_01(db, full):
    """MIL-INH-59 — a Python float 1.005 is stored as 1.01.
    Rules: `inherited` R1a"""
    result = dao.create(db, obj_in={**full, "unit_cost": 1.005})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("1.01")

# [claude] MIL-INH-60
def test_mil_inh_60__every_money_column_stores_2_decimals(db, full):
    """MIL-INH-60 — every money column stores 2 decimals.
    Rules: `inherited` R1a"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("1.005"), "total_cost": Decimal("1.005"), "value_before": Decimal("1.005"), "value_after": Decimal("1.005"), "avg_price_before": Decimal("1.005"), "avg_price_after": Decimal("1.005")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("1.01")
    assert row.total_cost == Decimal("1.01")
    # Then 3
    row = reread(db, result)
    assert row.value_before == Decimal("1.01")
    assert row.value_after == Decimal("1.01")
    # Then 4
    row = reread(db, result)
    assert row.avg_price_before == Decimal("1.01")
    assert row.avg_price_after == Decimal("1.01")

# [claude] MIL-INH-61
def test_mil_inh_61__the_instance_returned_by_create_keeps_the_given_value_until_it_is(db, full):
    """MIL-INH-61 — the instance returned by create keeps the given value until it is refreshed.
    Rules: `inherited` R1a"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("1.005")})

    # Then 1
    assert result.unit_cost == Decimal("1.005")
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("1.01")

# [claude] MIL-INH-62
def test_mil_inh_62__9999999999999_994_rounds_down_and_is_stored_as_9999999999999_99(db, full):
    """MIL-INH-62 — 9999999999999.994 rounds down and is stored as 9999999999999.99.
    Rules: `inherited` R1b"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("9999999999999.994")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("9999999999999.99")

# [claude] MIL-INH-63
def test_mil_inh_63__a_unit_cost_of_9999999999999_995_rounds_past_the_limit_and_nothing_is(db, full):
    """MIL-INH-63 — a unit_cost of 9999999999999.995 rounds past the limit and nothing is saved.
    Rules: `inherited` R1b, Errors row 5"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "unit_cost": Decimal("9999999999999.995")})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "numeric field overflow" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-INH-64
def test_mil_inh_64__a_total_cost_of_9999999999999_995_rounds_past_the_limit_and_nothing_is(db, full):
    """MIL-INH-64 — a total_cost of 9999999999999.995 rounds past the limit and nothing is saved.
    Rules: `inherited` R1b, Errors row 5"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "total_cost": Decimal("9999999999999.995")})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "numeric field overflow" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-INH-65
def test_mil_inh_65__a_value_before_of_9999999999999_995_rounds_past_the_limit_and_nothing(db, full):
    """MIL-INH-65 — a value_before of 9999999999999.995 rounds past the limit and nothing is saved.
    Rules: `inherited` R1b, Errors row 5"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "value_before": Decimal("9999999999999.995")})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "numeric field overflow" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-INH-66
def test_mil_inh_66__a_value_after_of_9999999999999_995_rounds_past_the_limit_and_nothing_is(db, full):
    """MIL-INH-66 — a value_after of 9999999999999.995 rounds past the limit and nothing is saved.
    Rules: `inherited` R1b, Errors row 5"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "value_after": Decimal("9999999999999.995")})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "numeric field overflow" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-INH-67
def test_mil_inh_67__an_avg_price_before_of_9999999999999_995_rounds_past_the_limit_and(db, full):
    """MIL-INH-67 — an avg_price_before of 9999999999999.995 rounds past the limit and nothing is saved.
    Rules: `inherited` R1b, Errors row 5"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "avg_price_before": Decimal("9999999999999.995")})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "numeric field overflow" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-INH-68
def test_mil_inh_68__an_avg_price_after_of_9999999999999_995_rounds_past_the_limit_and(db, full):
    """MIL-INH-68 — an avg_price_after of 9999999999999.995 rounds past the limit and nothing is saved.
    Rules: `inherited` R1b, Errors row 5"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "avg_price_after": Decimal("9999999999999.995")})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "numeric field overflow" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-INH-69
def test_mil_inh_69__the_most_negative_amount_a_cost_column_holds_is_saved(db, full):
    """MIL-INH-69 — the most negative amount a cost column holds is saved.
    Rules: `inherited` R1b"""
    result = dao.create(db, obj_in={**full, "unit_cost": Decimal("-9999999999999.99")})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.unit_cost == Decimal("-9999999999999.99")

# [claude] MIL-INH-70
def test_mil_inh_70__10000000000000_is_too_big_and_nothing_is_saved(db, full):
    """MIL-INH-70 — -10000000000000 is too big and nothing is saved.
    Rules: `inherited` R1b, Errors row 5"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "unit_cost": Decimal("-10000000000000")})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "numeric field overflow" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-INH-71
def test_mil_inh_71__the_greatest_integer_is_saved_in_quantity(db, full):
    """MIL-INH-71 — the greatest integer is saved in quantity.
    Rules: `inherited` R1b"""
    result = dao.create(db, obj_in={**full, "quantity": 2147483647})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.quantity == 2147483647

# [claude] MIL-INH-72
def test_mil_inh_72__the_smallest_integer_is_saved_in_quantity(db, full):
    """MIL-INH-72 — the smallest integer is saved in quantity.
    Rules: `inherited` R1b"""
    result = dao.create(db, obj_in={**full, "quantity": -2147483648})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.quantity == -2147483648

# [claude] MIL-INH-73
def test_mil_inh_73__a_quantity_of_2147483648_is_out_of_range_and_nothing_is_saved(db, full):
    """MIL-INH-73 — a quantity of 2147483648 is out of range and nothing is saved.
    Rules: `inherited` R1b, Errors row 6"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "quantity": 2147483648})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "integer out of range" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-INH-74
def test_mil_inh_74__a_quantity_of_2147483649_is_out_of_range_and_nothing_is_saved(db, full):
    """MIL-INH-74 — a quantity of -2147483649 is out of range and nothing is saved.
    Rules: `inherited` R1b, Errors row 6"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "quantity": -2147483649})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "integer out of range" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-INH-75
def test_mil_inh_75__a_qty_before_of_2147483648_is_out_of_range_and_nothing_is_saved(db, full):
    """MIL-INH-75 — a qty_before of 2147483648 is out of range and nothing is saved.
    Rules: `inherited` R1b, Errors row 6"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "qty_before": 2147483648})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "integer out of range" in str(exc.value.orig)
    # Then 5
    assert written(db) == before

# [claude] MIL-INH-76
def test_mil_inh_76__a_qty_after_of_2147483648_is_out_of_range_and_nothing_is_saved(db, full):
    """MIL-INH-76 — a qty_after of 2147483648 is out of range and nothing is saved.
    Rules: `inherited` R1b, Errors row 6"""
    before = written(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={**full, "qty_after": 2147483648})

    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert "integer out of range" in str(exc.value.orig)
    # Then 5
    assert written(db) == before


# [claude] MIL-INH-77
def test_mil_inh_77__machineitemledgercreate_ignores_workspace_id_and_performed_by_the_flush(db, w1, u1, m1, i1):
    """MIL-INH-77 — MachineItemLedgerCreate ignores workspace_id and performed_by: the flush still fails.
    Rules: `inherited` R2, Errors row 1"""
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=MachineItemLedgerCreate(machine_id=m1.id, item_id=i1.id, transaction_type="manual_add", quantity=3, unit_cost=Decimal("2.50"), total_cost=Decimal("7.50"), qty_before=4, qty_after=7, source_type="manual", workspace_id=w1.id, performed_by=u1.id))

    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "workspace_id"' in str(exc.value.orig)
    # Then 4
    assert written(db) == before


# [claude] MIL-INH-78
def test_mil_inh_78__machineitemledgercreate_rejects_a_negative_quantity(db, m1, i1):
    """MIL-INH-78 — MachineItemLedgerCreate rejects a negative quantity.
    Rules: `inherited` R2"""
    before = written(db)

    # Then 1
    with pytest.raises(ValidationError) as exc:
        MachineItemLedgerCreate(machine_id=m1.id, item_id=i1.id, transaction_type="manual_add", quantity=-1, unit_cost=Decimal("2.50"), total_cost=Decimal("7.50"), qty_before=4, qty_after=7, source_type="manual")

    # Then 2
    assert exc.value.errors()[0]["type"] == "greater_than_equal"
    # Then 3
    assert exc.value.errors()[0]["loc"] == ("quantity",)
    # Then 4
    assert written(db) == before


# [claude] MIL-INH-79
def test_mil_inh_79__machineitemledgercreate_rejects_a_negative_unit_cost(db, m1, i1):
    """MIL-INH-79 — MachineItemLedgerCreate rejects a negative unit_cost.
    Rules: `inherited` R2"""
    before = written(db)

    # Then 1
    with pytest.raises(ValidationError) as exc:
        MachineItemLedgerCreate(machine_id=m1.id, item_id=i1.id, transaction_type="manual_add", quantity=3, unit_cost=Decimal("-1.00"), total_cost=Decimal("7.50"), qty_before=4, qty_after=7, source_type="manual")

    # Then 2
    assert exc.value.errors()[0]["type"] == "greater_than_equal"
    # Then 3
    assert exc.value.errors()[0]["loc"] == ("unit_cost",)
    # Then 4
    assert written(db) == before


# [claude] MIL-INH-80
def test_mil_inh_80__machineitemledgercreate_rejects_a_negative_total_cost(db, m1, i1):
    """MIL-INH-80 — MachineItemLedgerCreate rejects a negative total_cost.
    Rules: `inherited` R2"""
    before = written(db)

    # Then 1
    with pytest.raises(ValidationError) as exc:
        MachineItemLedgerCreate(machine_id=m1.id, item_id=i1.id, transaction_type="manual_add", quantity=3, unit_cost=Decimal("2.50"), total_cost=Decimal("-1.00"), qty_before=4, qty_after=7, source_type="manual")

    # Then 2
    assert exc.value.errors()[0]["type"] == "greater_than_equal"
    # Then 3
    assert exc.value.errors()[0]["loc"] == ("total_cost",)
    # Then 4
    assert written(db) == before


# [claude] MIL-INH-81
def test_mil_inh_81__machineitemledgercreate_accepts_zero_quantity_and_costs_the_limit_is_at(db, m1, i1):
    """MIL-INH-81 — MachineItemLedgerCreate accepts zero quantity and costs: the limit is at least 0.
    Rules: `inherited` R2"""
    result = MachineItemLedgerCreate(machine_id=m1.id, item_id=i1.id, transaction_type="manual_add", quantity=0, unit_cost=Decimal("0.00"), total_cost=Decimal("0.00"), qty_before=4, qty_after=7, source_type="manual")

    # Then 1
    assert result.quantity == 0
    # Then 2
    assert result.unit_cost == Decimal("0.00")
    # Then 3
    assert result.total_cost == Decimal("0.00")

# --------------------------------------------------------------------------- #
# `GET /ledgers/machine/` response schema (`MachineItemLedgerResponse`)
# --------------------------------------------------------------------------- #

# [claude] MIL-RS-01
def test_mil_rs_01__a_stored_row_of_type_purchase_order_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-01 — a stored row of type "purchase_order" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="purchase_order")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "purchase_order"

# [claude] MIL-RS-02
def test_mil_rs_02__a_stored_row_of_type_manual_add_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-02 — a stored row of type "manual_add" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="manual_add")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "manual_add"

# [claude] MIL-RS-03
def test_mil_rs_03__a_stored_row_of_type_transfer_in_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-03 — a stored row of type "transfer_in" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="transfer_in")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "transfer_in"

# [claude] MIL-RS-04
def test_mil_rs_04__a_stored_row_of_type_transfer_out_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-04 — a stored row of type "transfer_out" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="transfer_out")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "transfer_out"

# [claude] MIL-RS-05
def test_mil_rs_05__a_stored_row_of_type_consumption_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-05 — a stored row of type "consumption" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="consumption")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "consumption"

# [claude] MIL-RS-06
def test_mil_rs_06__a_stored_row_of_type_damaged_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-06 — a stored row of type "damaged" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="damaged")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "damaged"

# [claude] MIL-RS-07
def test_mil_rs_07__a_stored_row_of_type_inventory_adjustment_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-07 — a stored row of type "inventory_adjustment" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="inventory_adjustment")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "inventory_adjustment"

# [claude] MIL-RS-08
def test_mil_rs_08__a_stored_row_of_type_cost_adjustment_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-08 — a stored row of type "cost_adjustment" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="cost_adjustment")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "cost_adjustment"

# [claude] MIL-RS-09
@pytest.mark.xfail(strict=True, reason="BUG-990: Machine ledger page crashes on returns, reversals and work-order movements")
def test_mil_rs_09__a_stored_row_of_type_purchase_return_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-09 — a stored row of type "purchase_return" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="purchase_return")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "purchase_return"

# [claude] MIL-RS-10
@pytest.mark.xfail(strict=True, reason="BUG-990: Machine ledger page crashes on returns, reversals and work-order movements")
def test_mil_rs_10__a_stored_row_of_type_consumption_reversal_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-10 — a stored row of type "consumption_reversal" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="consumption_reversal")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "consumption_reversal"

# [claude] MIL-RS-11
@pytest.mark.xfail(strict=True, reason="BUG-990: Machine ledger page crashes on returns, reversals and work-order movements")
def test_mil_rs_11__a_stored_row_of_type_work_order_install_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-11 — a stored row of type "work_order_install" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="work_order_install")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "work_order_install"

# [claude] MIL-RS-12
@pytest.mark.xfail(strict=True, reason="BUG-990: Machine ledger page crashes on returns, reversals and work-order movements")
def test_mil_rs_12__a_stored_row_of_type_work_order_replace_out_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-12 — a stored row of type "work_order_replace_out" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="work_order_replace_out")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "work_order_replace_out"

# [claude] MIL-RS-13
@pytest.mark.xfail(strict=True, reason="BUG-990: Machine ledger page crashes on returns, reversals and work-order movements")
def test_mil_rs_13__a_stored_row_of_type_work_order_replace_in_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-13 — a stored row of type "work_order_replace_in" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="work_order_replace_in")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "work_order_replace_in"

# [claude] MIL-RS-14
@pytest.mark.xfail(strict=True, reason="BUG-990: Machine ledger page crashes on returns, reversals and work-order movements")
def test_mil_rs_14__a_stored_row_of_type_work_order_borrow_returned_passes_and_keeps_its(db, mk_entry):
    """MIL-RS-14 — a stored row of type "work_order_borrow_returned" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="work_order_borrow_returned")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "work_order_borrow_returned"

# [claude] MIL-RS-15
@pytest.mark.xfail(strict=True, reason="BUG-990: Machine ledger page crashes on returns, reversals and work-order movements")
def test_mil_rs_15__a_stored_row_of_type_sale_passes_and_keeps_its_type(db, mk_entry):
    """MIL-RS-15 — a stored row of type "sale" passes and keeps its type.
    Rules: `GET /ledgers/machine/` R1"""
    e1 = mk_entry(performed_at=T1, transaction_type="sale")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert isinstance(result, MachineItemLedgerResponse)
    # Then 2
    assert result.transaction_type == "sale"

# [claude] MIL-RS-16
def test_mil_rs_16__a_stored_negative_quantity_is_rejected(db, mk_entry):
    """MIL-RS-16 — a stored negative quantity is rejected.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, quantity=-1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(ValidationError) as exc:
        MachineItemLedgerResponse.model_validate(e1)

    # Then 2
    assert exc.value.errors()[0]["type"] == "greater_than_equal"
    # Then 3
    assert exc.value.errors()[0]["loc"] == ("quantity",)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-RS-17
def test_mil_rs_17__a_stored_negative_unit_cost_is_rejected(db, mk_entry):
    """MIL-RS-17 — a stored negative unit_cost is rejected.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, unit_cost=Decimal("-2.00"))
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(ValidationError) as exc:
        MachineItemLedgerResponse.model_validate(e1)

    # Then 2
    assert exc.value.errors()[0]["type"] == "greater_than_equal"
    # Then 3
    assert exc.value.errors()[0]["loc"] == ("unit_cost",)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-RS-18
def test_mil_rs_18__a_stored_negative_total_cost_is_rejected(db, mk_entry):
    """MIL-RS-18 — a stored negative total_cost is rejected.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, total_cost=Decimal("-2.00"))
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(ValidationError) as exc:
        MachineItemLedgerResponse.model_validate(e1)

    # Then 2
    assert exc.value.errors()[0]["type"] == "greater_than_equal"
    # Then 3
    assert exc.value.errors()[0]["loc"] == ("total_cost",)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, e1) == before_e1

# [claude] MIL-RS-19
def test_mil_rs_19__zero_quantity_and_costs_pass_the_limit_is_at_least_0(db, mk_entry):
    """MIL-RS-19 — zero quantity and costs pass: the limit is at least 0.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, quantity=0, unit_cost=Decimal("0.00"), total_cost=Decimal("0.00"))

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert result.quantity == 0
    # Then 2
    assert result.unit_cost == Decimal("0.00")
    # Then 3
    assert result.total_cost == Decimal("0.00")

# [claude] MIL-RS-20
def test_mil_rs_20__a_negative_qty_after_passes(db, mk_entry):
    """MIL-RS-20 — a negative qty_after passes.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, qty_after=-3)

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert result.qty_after == -3

# [claude] MIL-RS-21
def test_mil_rs_21__a_negative_qty_before_passes(db, mk_entry):
    """MIL-RS-21 — a negative qty_before passes.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, qty_before=-3)

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert result.qty_before == -3

# [claude] MIL-RS-22
def test_mil_rs_22__a_negative_value_after_passes(db, mk_entry):
    """MIL-RS-22 — a negative value_after passes.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, value_after=Decimal("-12.50"))

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert result.value_after == Decimal("-12.50")

# [claude] MIL-RS-23
def test_mil_rs_23__a_negative_avg_price_after_passes(db, mk_entry):
    """MIL-RS-23 — a negative avg_price_after passes.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, avg_price_after=Decimal("-1.25"))

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert result.avg_price_after == Decimal("-1.25")

# [claude] MIL-RS-24
def test_mil_rs_24__any_source_type_passes(db, mk_entry):
    """MIL-RS-24 — any source_type passes.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, source_type="not a real source")

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert result.source_type == "not a real source"

# [claude] MIL-RS-25
def test_mil_rs_25__the_response_carries_the_required_fields_read_from_the_row_and_has_no(db, w1, u1, m1, i1, mk_entry):
    """MIL-RS-25 — the response carries the required fields read from the row and has no order_type.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1)

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert result.id == e1.id
    # Then 2
    assert result.workspace_id == w1.id
    # Then 3
    assert result.performed_by == u1.id
    # Then 4
    assert result.performed_at == T1
    # Then 5
    assert result.machine_id == m1.id
    assert result.item_id == i1.id
    # Then 6
    assert not hasattr(result, "order_type")


# [claude] MIL-RS-26
def test_mil_rs_26__the_other_ten_fields_are_read_from_the_row(db, mk_entry):
    """MIL-RS-26 — the other ten fields are read from the row.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, value_before=Decimal("7.00"), avg_price_before=Decimal("1.75"), source_id=77, order_id=88, notes="Counted", transfer_source_type="machine", transfer_source_id=11, transfer_destination_type="storage", transfer_destination_id=12)
    e1.invoice_id = 99

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert result.value_before == Decimal("7.00")
    # Then 2
    assert result.avg_price_before == Decimal("1.75")
    # Then 3
    assert result.source_id == 77
    # Then 4
    assert result.order_id == 88
    # Then 5
    assert result.invoice_id == 99
    # Then 6
    assert result.notes == "Counted"
    # Then 7
    assert result.transfer_source_type == "machine"
    # Then 8
    assert result.transfer_source_id == 11
    # Then 9
    assert result.transfer_destination_type == "storage"
    # Then 10
    assert result.transfer_destination_id == 12


# [claude] MIL-RS-27
def test_mil_rs_27__a_negative_value_before_passes(db, mk_entry):
    """MIL-RS-27 — a negative value_before passes.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, value_before=Decimal("-12.50"))

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert result.value_before == Decimal("-12.50")


# [claude] MIL-RS-28
def test_mil_rs_28__a_negative_avg_price_before_passes(db, mk_entry):
    """MIL-RS-28 — a negative avg_price_before passes.
    Rules: `GET /ledgers/machine/` R1a"""
    e1 = mk_entry(performed_at=T1, avg_price_before=Decimal("-1.25"))

    result = MachineItemLedgerResponse.model_validate(e1)

    # Then 1
    assert result.avg_price_before == Decimal("-1.25")
