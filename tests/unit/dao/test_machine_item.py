"""Unit tests for app/dao/machine_item.py.

Implements tests/unit/dao/machine_item.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock is
patched (Conventions, Externals: None); the commit spy of the "rolled back"
cards wraps the real `db.commit`.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from unittest.mock import patch

import pytest
from psycopg2.errors import (
    ForeignKeyViolation,
    InvalidRowCountInLimitClause,
    InvalidRowCountInResultOffsetClause,
    NotNullViolation,
    NumericValueOutOfRange,
    UniqueViolation,
)
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.machine_item import machine_item_dao
from app.models.factory import Factory
from app.models.item import Item
from app.models.machine import Machine
from app.models.machine_item import MachineItem
from app.schemas.machine_item import MachineItemCreate, MachineItemUpdate
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton machine_item_dao" (a module-level name, not a fixture)
dao = machine_item_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999


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


def _item(db, workspace, name, unit, **columns):
    fields = {"workspace_id": workspace.id, "name": name, "name_normalized": name.lower(),
              "unit": unit, "is_active": True}
    fields.update(columns)
    return _add(db, Item(**fields))


# Convention "W1, W2 = two workspaces rows". w2 depends on w1, so the ids rise in
# the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


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


# Convention "M1, M2, M3"
@pytest.fixture
def m1(db, w1, f1):
    return _machine(db, w1, f1, "Press 1")


@pytest.fixture
def m2(db, w1, f1):
    return _machine(db, w1, f1, "Press 2")


@pytest.fixture
def m3(db, w1, f1):
    return _machine(db, w1, f1, "Press 3")


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


# Convention "I1, I2, I3"
@pytest.fixture
def i1(db, w1):
    return _item(db, w1, "Bolt", "pcs")


@pytest.fixture
def i2(db, w1):
    return _item(db, w1, "Washer", "kg")


@pytest.fixture
def i3(db, w1):
    return _item(db, w1, "Spring", "box")


# Convention "IX": removed
@pytest.fixture
def ix(db, w1):
    return _item(db, w1, "Old Gasket", "m", is_active=False)


# Convention "I9"
@pytest.fixture
def i9(db, w2):
    return _item(db, w2, "Far Crate", "set")


# Convention "These rows exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, f1, fd, fi, f9, m1, m2, m3, md, mi, mf, mg, m9, i1, i2, i3, ix, i9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (fixtures; each flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "stock": workspace W1, qty 5, req_qty None, defective_qty None
@pytest.fixture
def mk_stock(db, w1):
    """mk_stock(machine_id=..., item_id=..., **columns) -> MachineItem. Keywords only."""
    def _mk(*, machine_id, item_id, **columns):
        fields = {"workspace_id": w1.id, "machine_id": machine_id, "item_id": item_id,
                  "qty": 5, "req_qty": None, "defective_qty": None}
        fields.update(columns)
        return _add(db, MachineItem(**fields))
    return _mk


# Convention "item" (a further row in a Given): workspace W1 and the columns the card lists
@pytest.fixture
def mk_item(db, w1):
    """mk_item(**columns) -> Item. Keywords only."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id}
        fields.update(columns)
        return _add(db, Item(**fields))
    return _mk


# The "N1 ... N101 items, S1 ... S101 stock rows" Given of the page-size cards
@pytest.fixture
def mk_part_stock(db, w1, m1):
    """mk_part_stock(count) -> the ids of `count` stock rows of M1, one item each, Sk on Nk."""
    def _mk(count):
        parts = [
            _add(db, Item(workspace_id=w1.id, name=f"Part {k:03d}", name_normalized=f"part {k:03d}",
                          unit="pcs", is_active=True))
            for k in range(1, count + 1)
        ]
        rows = [MachineItem(workspace_id=w1.id, machine_id=m1.id, item_id=part.id, qty=5,
                            req_qty=None, defective_qty=None) for part in parts]
        db.add_all(rows)
        db.flush()
        return [row.id for row in rows]
    return _mk


# The "P1 ... P501 machines, S1 ... S501 stock rows" Given of MIT-GT-25 and MIT-GT-26
@pytest.fixture
def mk_press_stock(db, w1, f1, i1):
    """mk_press_stock(count) -> the ids of `count` stock rows of I1, one machine each, Sk on Pk."""
    def _mk(count):
        presses = [Machine(workspace_id=w1.id, factory_id=f1.id, name=f"Press {k:03d}",
                           is_active=True, is_deleted=False) for k in range(1, count + 1)]
        db.add_all(presses)
        db.flush()
        rows = [MachineItem(workspace_id=w1.id, machine_id=press.id, item_id=i1.id, qty=5,
                            req_qty=None, defective_qty=None) for press in presses]
        db.add_all(rows)
        db.flush()
        return [row.id for row in rows]
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

def _id_of(row):
    """Primary key of a row, without touching its (possibly expired) attributes."""
    return sa_inspect(row).identity[0]


# Convention "ids(result)" / "item_names(result)": in the order returned
def ids(result):
    return [row.id for row in result]


def item_names(result):
    return [row.item_name for row in result]


# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row):
    """Fresh copy of the stock row `row` from the database, or None if it is gone."""
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(MachineItem).where(MachineItem.id == row_id)).unique().scalar_one_or_none()


# Convention "unchanged(X)": every column of X (of any table), straight from the table
def snap(db, row):
    """Dict column -> database value of `row`, or None if it is gone."""
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == _id_of(row))).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "count:" lines: rows of machine_items in all workspaces, with the filter stated
def count_rows(db, **where):
    table = MachineItem.__table__
    stmt = select(func.count()).select_from(table)
    for column, value in where.items():
        stmt = stmt.where(table.c[column] == value)
    return db.execute(stmt).scalar_one()


# Convention "nothing written": the number of machine_items rows (all workspaces)
def written(db):
    return count_rows(db)


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
# DAOMachineItem.get_by_workspace
# --------------------------------------------------------------------------- #


# [claude] MIT-GW-01
def test_mit_gw_01__returns_a_list_of_the_workspace_s_stock_rows_and_writes_nothing(db, w1, m1, m2, i1, i2, mk_stock):
    """MIT-GW-01 — returns a list of the workspace's stock rows and writes nothing.
    Rules: `get_by_workspace` R1, Returns, Side effects"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    c = mk_stock(machine_id=m2.id, item_id=i1.id)
    before = written(db)
    before_a = snap(db, a)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id, c.id]
    # Then 3
    assert isinstance(result[0], MachineItem)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a) == before_a


# [claude] MIT-GW-02
def test_mit_gw_02__a_row_of_another_workspace_does_not_appear_although_it_would_fit_on_the(db, w1, w2, m1, m9, i1, i9, mk_stock):
    """MIT-GW-02 — a row of another workspace does not appear, although it would fit on the page.
    Rules: `get_by_workspace` R1"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    z = mk_stock(machine_id=m9.id, item_id=i9.id, workspace_id=w2.id)
    before_z = snap(db, z)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert snap(db, z) == before_z


# [claude] MIT-GW-03
def test_mit_gw_03__the_other_workspace_gets_only_its_own_row(db, w2, m1, m9, i1, i9, mk_stock):
    """MIT-GW-03 — the other workspace gets only its own row.
    Rules: `get_by_workspace` R1"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    z = mk_stock(machine_id=m9.id, item_id=i9.id, workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [z.id]


# [claude] MIT-GW-04
def test_mit_gw_04__the_same_machine_and_item_in_two_workspaces_w1_gets_only_its_own_row(db, w1, w2, m1, i1, mk_stock):
    """MIT-GW-04 — the same machine and item in two workspaces: W1 gets only its own row.
    Rules: `get_by_workspace` R1"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MIT-GW-05
def test_mit_gw_05__the_same_machine_and_item_in_two_workspaces_w2_gets_only_its_own_row(db, w2, m1, i1, mk_stock):
    """MIT-GW-05 — the same machine and item in two workspaces: W2 gets only its own row.
    Rules: `get_by_workspace` R1"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    z = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [z.id]


# [claude] MIT-GW-06
def test_mit_gw_06__rows_are_returned_whatever_their_quantities(db, w1, m1, i1, i2, i3, mk_stock):
    """MIT-GW-06 — rows are returned whatever their quantities.
    Rules: `get_by_workspace` R2"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id, qty=0)
    b = mk_stock(machine_id=m1.id, item_id=i2.id, qty=-4)
    c = mk_stock(machine_id=m1.id, item_id=i3.id, qty=3, req_qty=9, defective_qty=1)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]


# [claude] MIT-GW-07
def test_mit_gw_07__the_row_of_a_soft_deleted_machine_is_returned_and_left_as_it_was(db, w1, m1, md, i1, mk_stock):
    """MIT-GW-07 — the row of a soft-deleted machine is returned and left as it was.
    Rules: `get_by_workspace` R2"""
    a = mk_stock(machine_id=md.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i1.id)
    before_a = snap(db, a)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIT-GW-08
def test_mit_gw_08__the_row_of_a_machine_in_a_soft_deleted_factory_is_returned_and_left_as(db, w1, m1, mf, i1, mk_stock):
    """MIT-GW-08 — the row of a machine in a soft-deleted factory is returned and left as it was.
    Rules: `get_by_workspace` R2"""
    a = mk_stock(machine_id=mf.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i1.id)
    before_a = snap(db, a)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIT-GW-09
def test_mit_gw_09__the_row_of_a_removed_item_is_returned_and_left_as_it_was(db, w1, m1, i1, ix, mk_stock):
    """MIT-GW-09 — the row of a removed item is returned and left as it was.
    Rules: `get_by_workspace` R2"""
    a = mk_stock(machine_id=m1.id, item_id=ix.id)
    b = mk_stock(machine_id=m1.id, item_id=i1.id)
    before_a = snap(db, a)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIT-GW-10
def test_mit_gw_10__rows_of_deleted_parents_take_a_place_in_the_page(db, w1, m1, md, mf, i1, ix, mk_stock):
    """MIT-GW-10 — rows of deleted parents take a place in the page.
    Rules: `get_by_workspace` R2"""
    a = mk_stock(machine_id=md.id, item_id=i1.id)
    b = mk_stock(machine_id=mf.id, item_id=i1.id)
    c = mk_stock(machine_id=m1.id, item_id=ix.id)
    d = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=3)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {a.id, b.id, c.id, d.id}


# [claude] MIT-GW-11
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gw_11__rows_come_back_in_id_order(db, w1, m1, i1, i2, mk_stock):
    """MIT-GW-11 — rows come back in id order.
    Rules: `get_by_workspace` R3 [BUG-100]"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    a.qty = 6
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] MIT-GW-12
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gw_12__the_first_of_two_windows_holds_the_two_lowest_ids(db, w1, m1, m2, i1, i2, i3, mk_stock):
    """MIT-GW-12 — the first of two windows holds the two lowest ids.
    Rules: `get_by_workspace` R3 [BUG-100], R4"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    mk_stock(machine_id=m1.id, item_id=i3.id)
    mk_stock(machine_id=m2.id, item_id=i1.id)
    a.qty = 6
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] MIT-GW-13
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gw_13__the_second_of_two_windows_holds_the_two_highest_ids(db, w1, m1, m2, i1, i2, i3, mk_stock):
    """MIT-GW-13 — the second of two windows holds the two highest ids.
    Rules: `get_by_workspace` R3 [BUG-100], R4"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i2.id)
    c = mk_stock(machine_id=m1.id, item_id=i3.id)
    d = mk_stock(machine_id=m2.id, item_id=i1.id)
    a.qty = 6
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert ids(result) == [c.id, d.id]


# [claude] MIT-GW-14
@pytest.mark.xfail(strict=True, reason="BUG-100: BaseDAO list methods have no sort order")
def test_mit_gw_14__the_workspace_list_query_asks_the_database_for_id_order(db, w1, m1, i1, mk_stock):
    """MIT-GW-14 — the workspace list query asks the database for id order.
    Rules: `get_by_workspace` R3 [BUG-100]"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1.id)
    [sql] = recorder.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_items.id" in order_part
    # Then 4
    assert "DESC" not in order_part


# [claude] MIT-GW-15
def test_mit_gw_15__with_the_default_limit_101_rows_give_exactly_100(db, w1, mk_part_stock):
    """MIT-GW-15 — with the default limit 101 rows give exactly 100.
    Rules: `get_by_workspace` R4"""
    all_ids = mk_part_stock(101)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert set(ids(result)) <= set(all_ids)


# [claude] MIT-GW-16
def test_mit_gw_16__with_the_default_limit_100_rows_give_all_100(db, w1, mk_part_stock):
    """MIT-GW-16 — with the default limit 100 rows give all 100.
    Rules: `get_by_workspace` R4"""
    all_ids = mk_part_stock(100)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert sorted(ids(result)) == sorted(all_ids)


# [claude] MIT-GW-17
def test_mit_gw_17__an_explicit_limit_of_101_gives_all_101_rows(db, w1, mk_part_stock):
    """MIT-GW-17 — an explicit limit of 101 gives all 101 rows.
    Rules: `get_by_workspace` R4"""
    all_ids = mk_part_stock(101)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(all_ids)


# [claude] MIT-GW-18
def test_mit_gw_18__limit_2_of_three_rows_gives_two_of_them(db, w1, m1, i1, i2, i3, mk_stock):
    """MIT-GW-18 — limit=2 of three rows gives two of them.
    Rules: `get_by_workspace` R4"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    c = mk_stock(machine_id=m1.id, item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert set(ids(result)) <= {a.id, b.id, c.id}


# [claude] MIT-GW-19
def test_mit_gw_19__skip_1_of_three_rows_gives_two_of_them(db, w1, m1, i1, i2, i3, mk_stock):
    """MIT-GW-19 — skip=1 of three rows gives two of them.
    Rules: `get_by_workspace` R4"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    c = mk_stock(machine_id=m1.id, item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert set(ids(result)) <= {a.id, b.id, c.id}


# [claude] MIT-GW-20
def test_mit_gw_20__skip_1_and_limit_1_of_three_rows_gives_one_of_them(db, w1, m1, i1, i2, i3, mk_stock):
    """MIT-GW-20 — skip=1 and limit=1 of three rows gives one of them.
    Rules: `get_by_workspace` R4"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    c = mk_stock(machine_id=m1.id, item_id=i3.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {a.id, b.id, c.id}


# [claude] MIT-GW-21
def test_mit_gw_21__an_unknown_workspace_returns_an_empty_list(db, m1, i1, mk_stock):
    """MIT-GW-21 — an unknown workspace returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_workspace(db, workspace_id=MISSING)

    # Then 1
    assert result == []


# [claude] MIT-GW-22
def test_mit_gw_22__a_workspace_with_no_rows_returns_an_empty_list(db, w2, m1, i1, mk_stock):
    """MIT-GW-22 — a workspace with no rows returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MIT-GW-23
def test_mit_gw_23__skip_equal_to_the_number_of_rows_returns_an_empty_list(db, w1, m1, i1, i2, mk_stock):
    """MIT-GW-23 — skip equal to the number of rows returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MIT-GW-24
def test_mit_gw_24__skip_past_the_number_of_rows_returns_an_empty_list(db, w1, m1, i1, i2, mk_stock):
    """MIT-GW-24 — skip past the number of rows returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []


# [claude] MIT-GW-25
def test_mit_gw_25__skip_one_below_the_number_of_rows_returns_one_row(db, w1, m1, i1, i2, mk_stock):
    """MIT-GW-25 — skip one below the number of rows returns one row.
    Rules: `get_by_workspace` R5, R4"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {a.id, b.id}


# [claude] MIT-GW-26
def test_mit_gw_26__limit_0_returns_an_empty_list(db, w1, m1, i1, i2, mk_stock):
    """MIT-GW-26 — limit=0 returns an empty list.
    Rules: `get_by_workspace` R5"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] MIT-GW-27
def test_mit_gw_27__limit_1_returns_one_row(db, w1, m1, i1, i2, mk_stock):
    """MIT-GW-27 — limit=1 returns one row.
    Rules: `get_by_workspace` R5, R4"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {a.id, b.id}


# [claude] MIT-GW-28
def test_mit_gw_28__a_negative_limit_is_rejected_by_postgres(db, w1, m1, i1, mk_stock):
    """MIT-GW-28 — a negative limit is rejected by Postgres.
    Rules: `get_by_workspace` R6, Errors row 1"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
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


# [claude] MIT-GW-29
def test_mit_gw_29__a_negative_skip_is_rejected_by_postgres(db, w1, m1, i1, mk_stock):
    """MIT-GW-29 — a negative skip is rejected by Postgres.
    Rules: `get_by_workspace` R6, Errors row 2"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
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


# [claude] MIT-GW-30
def test_mit_gw_30__a_row_carries_the_name_and_unit_of_its_item(db, w1, m1, i1, mk_stock):
    """MIT-GW-30 — a row carries the name and unit of its item.
    Rules: `get_by_workspace` R7"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].item_name == "Bolt"
    # Then 3
    assert result[0].item_unit == "pcs"


# [claude] MIT-GW-31
def test_mit_gw_31__a_row_of_a_removed_item_carries_that_item_s_name_and_unit(db, w1, m1, ix, mk_stock):
    """MIT-GW-31 — a row of a removed item carries that item's name and unit.
    Rules: `get_by_workspace` R7"""
    a = mk_stock(machine_id=m1.id, item_id=ix.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].item_name == "Old Gasket"
    # Then 3
    assert result[0].item_unit == "m"


# [claude] MIT-GW-32
def test_mit_gw_32__reading_a_row_s_item_name_and_unit_needs_no_further_query(db, w1, m1, i1, mk_stock):
    """MIT-GW-32 — reading a row's item name and unit needs no further query.
    Rules: `get_by_workspace` R7"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    w1_id = w1.id
    db.expire_all()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_workspace(db, workspace_id=w1_id)

        # Then 1
        assert result[0].item_name == "Bolt"
        # Then 2
        assert result[0].item_unit == "pcs"
        # Then 3
        assert len(recorder.selects()) == 1


# [claude] MIT-GW-33
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gw_33__id_order_holds_when_the_lower_id_sits_on_the_higher_machine_and_item(db, w1, m1, m2, i1, i2, mk_stock):
    """MIT-GW-33 — id order holds when the lower id sits on the higher machine and item.
    Rules: `get_by_workspace` R3 [BUG-100]"""
    a = mk_stock(machine_id=m2.id, item_id=i2.id)
    b = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert ids(result) == [a.id, b.id]


# --------------------------------------------------------------------------- #
# DAOMachineItem.get_by_id_and_workspace
# --------------------------------------------------------------------------- #


# [claude] MIT-GI-01
def test_mit_gi_01__returns_the_session_s_row_with_that_id_and_writes_nothing(db, w1, m1, i1, i2, mk_stock):
    """MIT-GI-01 — returns the session's row with that id and writes nothing.
    Rules: `get_by_id_and_workspace` R1, Returns, Side effects"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    before = written(db)
    before_b = snap(db, b)

    result = dao.get_by_id_and_workspace(db, id=b.id, workspace_id=w1.id)

    # Then 1
    assert result is b
    # Then 2
    assert isinstance(result, MachineItem)
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, b) == before_b


# [claude] MIT-GI-02
def test_mit_gi_02__a_row_of_another_workspace_is_not_found(db, w1, w2, m9, i9, mk_stock):
    """MIT-GI-02 — a row of another workspace is not found.
    Rules: `get_by_id_and_workspace` R2"""
    z = mk_stock(machine_id=m9.id, item_id=i9.id, workspace_id=w2.id)
    before_z = snap(db, z)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert snap(db, z) == before_z


# [claude] MIT-GI-03
def test_mit_gi_03__a_w1_row_asked_for_under_w2_is_not_found(db, w2, m1, i1, mk_stock):
    """MIT-GI-03 — a W1 row asked for under W2 is not found.
    Rules: `get_by_id_and_workspace` R2"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w2.id)

    # Then 1
    assert result is None


# [claude] MIT-GI-04
def test_mit_gi_04__a_row_is_found_under_its_own_workspace(db, w2, m9, i9, mk_stock):
    """MIT-GI-04 — a row is found under its own workspace.
    Rules: `get_by_id_and_workspace` R1, R2"""
    z = mk_stock(machine_id=m9.id, item_id=i9.id, workspace_id=w2.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w2.id)

    # Then 1
    assert result is z


# [claude] MIT-GI-05
def test_mit_gi_05__the_w2_row_of_a_machine_and_item_w1_also_holds_is_not_found_under_w1(db, w1, w2, m1, i1, mk_stock):
    """MIT-GI-05 — the W2 row of a machine and item W1 also holds is not found under W1.
    Rules: `get_by_id_and_workspace` R2"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    z = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_id_and_workspace(db, id=z.id, workspace_id=w1.id)

    # Then 1
    assert result is None


# [claude] MIT-GI-06
def test_mit_gi_06__an_unknown_workspace_finds_nothing(db, m1, i1, mk_stock):
    """MIT-GI-06 — an unknown workspace finds nothing.
    Rules: `get_by_id_and_workspace` R2"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=MISSING)

    # Then 1
    assert result is None


# [claude] MIT-GI-07
def test_mit_gi_07__an_unknown_id_returns_none_and_writes_nothing(db, w1, m1, i1, mk_stock):
    """MIT-GI-07 — an unknown id returns None and writes nothing.
    Rules: `get_by_id_and_workspace` R3"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    before = written(db)

    result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before


# [claude] MIT-GI-08
def test_mit_gi_08__id_0_returns_none_and_writes_nothing(db, w1, m1, i1, mk_stock):
    """MIT-GI-08 — id=0 returns None and writes nothing.
    Rules: `get_by_id_and_workspace` R3"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    before = written(db)

    result = dao.get_by_id_and_workspace(db, id=0, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before


# [claude] MIT-GI-09
def test_mit_gi_09__the_row_of_a_soft_deleted_machine_is_found(db, w1, md, i1, mk_stock):
    """MIT-GI-09 — the row of a soft-deleted machine is found.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_stock(machine_id=md.id, item_id=i1.id)
    before_a = snap(db, a)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIT-GI-10
def test_mit_gi_10__the_row_of_a_machine_in_a_soft_deleted_factory_is_found(db, w1, mf, i1, mk_stock):
    """MIT-GI-10 — the row of a machine in a soft-deleted factory is found.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_stock(machine_id=mf.id, item_id=i1.id)
    before_a = snap(db, a)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIT-GI-11
def test_mit_gi_11__the_row_of_a_removed_item_is_found(db, w1, m1, ix, mk_stock):
    """MIT-GI-11 — the row of a removed item is found.
    Rules: `get_by_id_and_workspace` R4"""
    a = mk_stock(machine_id=m1.id, item_id=ix.id)
    before_a = snap(db, a)

    result = dao.get_by_id_and_workspace(db, id=a.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert snap(db, a) == before_a

# --------------------------------------------------------------------------- #
# DAOMachineItem.get_by_machine
# --------------------------------------------------------------------------- #


# [claude] MIT-GM-01
def test_mit_gm_01__returns_a_list_of_the_machine_s_rows_and_writes_nothing(db, w1, m1, i1, i2, mk_stock):
    """MIT-GM-01 — returns a list of the machine's rows and writes nothing.
    Rules: `get_by_machine` R1, Returns, Side effects"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    before = written(db)
    before_a = snap(db, a)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], MachineItem)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a) == before_a


# [claude] MIT-GM-02
def test_mit_gm_02__a_row_of_another_machine_is_not_returned(db, w1, m1, m2, i1, mk_stock):
    """MIT-GM-02 — a row of another machine is not returned.
    Rules: `get_by_machine` R1"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    c = mk_stock(machine_id=m2.id, item_id=i1.id)
    before_c = snap(db, c)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert snap(db, c) == before_c


# [claude] MIT-GM-03
def test_mit_gm_03__the_other_machine_gets_only_its_own_row(db, w1, m1, m2, i1, mk_stock):
    """MIT-GM-03 — the other machine gets only its own row.
    Rules: `get_by_machine` R1"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    c = mk_stock(machine_id=m2.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=m2.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MIT-GM-04
def test_mit_gm_04__rows_of_another_machine_or_workspace_take_no_place_in_the_page(db, w1, w2, m1, m2, i1, i2, mk_stock):
    """MIT-GM-04 — rows of another machine or workspace take no place in the page.
    Rules: `get_by_machine` R1, R2"""
    mk_stock(machine_id=m2.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MIT-GM-05
def test_mit_gm_05__the_right_machine_under_another_workspace_returns_an_empty_list(db, w2, m1, i1, mk_stock):
    """MIT-GM-05 — the right machine under another workspace returns an empty list.
    Rules: `get_by_machine` R2"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MIT-GM-06
def test_mit_gm_06__a_w2_row_on_a_machine_of_w1_is_returned_for_w2(db, w2, m1, i1, mk_stock):
    """MIT-GM-06 — a W2 row on a machine of W1 is returned for W2.
    Rules: `get_by_machine` R2"""
    z = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [z.id]


# [claude] MIT-GM-07
def test_mit_gm_07__a_w2_row_on_a_machine_of_w1_is_not_returned_for_w1(db, w1, w2, m1, i1, mk_stock):
    """MIT-GM-07 — a W2 row on a machine of W1 is not returned for W1.
    Rules: `get_by_machine` R2"""
    mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GM-08
def test_mit_gm_08__the_same_machine_and_item_in_two_workspaces_w1_gets_only_its_own_row(db, w1, w2, m1, i1, mk_stock):
    """MIT-GM-08 — the same machine and item in two workspaces: W1 gets only its own row.
    Rules: `get_by_machine` R2"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MIT-GM-09
def test_mit_gm_09__the_same_machine_and_item_in_two_workspaces_w2_gets_only_its_own_row(db, w2, m1, i1, mk_stock):
    """MIT-GM-09 — the same machine and item in two workspaces: W2 gets only its own row.
    Rules: `get_by_machine` R2"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    z = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [z.id]


# [claude] MIT-GM-10
def test_mit_gm_10__a_w1_row_on_a_machine_of_w2_is_returned_for_w1(db, w1, m9, i1, mk_stock):
    """MIT-GM-10 — a W1 row on a machine of W2 is returned for W1.
    Rules: `get_by_machine` R2"""
    a = mk_stock(machine_id=m9.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=m9.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MIT-GM-11
def test_mit_gm_11__a_w1_row_of_an_item_of_w2_is_returned_for_w1(db, w1, m1, i9, mk_stock):
    """MIT-GM-11 — a W1 row of an item of W2 is returned for W1.
    Rules: `get_by_machine` R2"""
    a = mk_stock(machine_id=m1.id, item_id=i9.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MIT-GM-12
def test_mit_gm_12__rows_are_returned_whatever_their_quantities(db, w1, m1, i1, i2, i3, mk_stock):
    """MIT-GM-12 — rows are returned whatever their quantities.
    Rules: `get_by_machine` R3"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id, qty=0)
    b = mk_stock(machine_id=m1.id, item_id=i2.id, qty=-4)
    c = mk_stock(machine_id=m1.id, item_id=i3.id, qty=3, req_qty=9, defective_qty=1)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]


# [claude] MIT-GM-13
def test_mit_gm_13__an_unknown_machine_id_returns_an_empty_list(db, w1, m1, i1, mk_stock):
    """MIT-GM-13 — an unknown machine id returns an empty list.
    Rules: `get_by_machine` R4"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GM-14
def test_mit_gm_14__machine_id_0_returns_an_empty_list(db, w1, m1, i1, mk_stock):
    """MIT-GM-14 — machine_id=0 returns an empty list.
    Rules: `get_by_machine` R4"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GM-15
def test_mit_gm_15__a_machine_with_no_rows_returns_an_empty_list(db, w1, m1, m2, i1, mk_stock):
    """MIT-GM-15 — a machine with no rows returns an empty list.
    Rules: `get_by_machine` R4"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=m2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GM-16
@pytest.mark.xfail(strict=True, reason="BUG-979: A machine's stock list still shows a deleted machine, or a machine of a deleted factory")
def test_mit_gm_16__the_rows_of_a_soft_deleted_machine_are_hidden(db, w1, m1, md, i1, mk_stock):
    """MIT-GM-16 — the rows of a soft-deleted machine are hidden.
    Rules: `get_by_machine` R4a [BUG-979]"""
    mk_stock(machine_id=md.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=md.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GM-17
@pytest.mark.xfail(strict=True, reason="BUG-979: A machine's stock list still shows a deleted machine, or a machine of a deleted factory")
def test_mit_gm_17__a_w2_row_on_a_soft_deleted_machine_of_w1_is_hidden_too(db, w2, md, i1, mk_stock):
    """MIT-GM-17 — a W2 row on a soft-deleted machine of W1 is hidden too.
    Rules: `get_by_machine` R4a [BUG-979], R2"""
    mk_stock(machine_id=md.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=md.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MIT-GM-18
@pytest.mark.xfail(strict=True, reason="BUG-979: A machine's stock list still shows a deleted machine, or a machine of a deleted factory")
def test_mit_gm_18__the_rows_of_a_live_machine_in_a_soft_deleted_factory_are_hidden(db, w1, m1, mf, i1, mk_stock):
    """MIT-GM-18 — the rows of a live machine in a soft-deleted factory are hidden.
    Rules: `get_by_machine` R4b [BUG-979]"""
    mk_stock(machine_id=mf.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=mf.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GM-19
def test_mit_gm_19__listing_a_soft_deleted_machine_changes_nothing(db, w1, md, i1, mk_stock):
    """MIT-GM-19 — listing a soft-deleted machine changes nothing.
    Rules: `get_by_machine` R4c"""
    a = mk_stock(machine_id=md.id, item_id=i1.id, req_qty=7, defective_qty=1)
    before = written(db)
    before_a = snap(db, a)
    before_md = snap(db, md)

    result = dao.get_by_machine(db, machine_id=md.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert snap(db, md) == before_md
    # Then 4
    assert written(db) == before


# [claude] MIT-GM-20
def test_mit_gm_20__listing_a_machine_in_a_soft_deleted_factory_changes_nothing(db, w1, fd, mf, i1, mk_stock):
    """MIT-GM-20 — listing a machine in a soft-deleted factory changes nothing.
    Rules: `get_by_machine` R4c"""
    a = mk_stock(machine_id=mf.id, item_id=i1.id, req_qty=7, defective_qty=1)
    before = written(db)
    before_a = snap(db, a)
    before_mf = snap(db, mf)
    before_fd = snap(db, fd)

    result = dao.get_by_machine(db, machine_id=mf.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert snap(db, mf) == before_mf
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    assert written(db) == before


# [claude] MIT-GM-21
def test_mit_gm_21__an_inactive_but_live_machine_hides_nothing(db, w1, mi, i1, mk_stock):
    """MIT-GM-21 — an inactive but live machine hides nothing.
    Rules: `get_by_machine` R4c"""
    a = mk_stock(machine_id=mi.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=mi.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MIT-GM-22
def test_mit_gm_22__a_live_machine_in_an_inactive_but_live_factory_hides_nothing(db, w1, mg, i1, mk_stock):
    """MIT-GM-22 — a live machine in an inactive but live factory hides nothing.
    Rules: `get_by_machine` R4c"""
    a = mk_stock(machine_id=mg.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=mg.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MIT-GM-23
def test_mit_gm_23__the_rows_are_back_unchanged_once_the_machine_is_no_longer_deleted(db, w1, md, i1, mk_stock):
    """MIT-GM-23 — the rows are back, unchanged, once the machine is no longer deleted.
    Rules: `get_by_machine` R4c"""
    a = mk_stock(machine_id=md.id, item_id=i1.id, req_qty=7)
    before_a = snap(db, a)
    md.is_deleted = False
    md.is_active = True
    db.flush()

    result = dao.get_by_machine(db, machine_id=md.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    row = reread(db, a)
    assert row.qty == 5
    assert row.req_qty == 7


# [claude] MIT-GM-24
def test_mit_gm_24__the_rows_are_back_unchanged_once_the_factory_is_no_longer_deleted(db, w1, fd, mf, i1, mk_stock):
    """MIT-GM-24 — the rows are back, unchanged, once the factory is no longer deleted.
    Rules: `get_by_machine` R4c"""
    a = mk_stock(machine_id=mf.id, item_id=i1.id, req_qty=7)
    before_a = snap(db, a)
    fd.is_deleted = False
    db.flush()

    result = dao.get_by_machine(db, machine_id=mf.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    row = reread(db, a)
    assert row.qty == 5
    assert row.req_qty == 7


# [claude] MIT-GM-25
@pytest.mark.xfail(strict=True, reason="BUG-980: A machine's stock list still shows items removed from the catalog")
def test_mit_gm_25__the_row_of_a_removed_item_is_not_returned_the_other_row_is(db, w1, m1, i1, ix, mk_stock):
    """MIT-GM-25 — the row of a removed item is not returned, the other row is.
    Rules: `get_by_machine` R5 [BUG-980]"""
    mk_stock(machine_id=m1.id, item_id=ix.id)
    b = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [b.id]


# [claude] MIT-GM-26
@pytest.mark.xfail(strict=True, reason="BUG-980: A machine's stock list still shows items removed from the catalog")
def test_mit_gm_26__a_machine_holding_only_a_removed_item_returns_an_empty_list(db, w1, m1, ix, mk_stock):
    """MIT-GM-26 — a machine holding only a removed item returns an empty list.
    Rules: `get_by_machine` R5 [BUG-980]"""
    mk_stock(machine_id=m1.id, item_id=ix.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GM-27
@pytest.mark.xfail(strict=True, reason="BUG-980: A machine's stock list still shows items removed from the catalog")
def test_mit_gm_27__the_row_of_a_removed_item_takes_no_place_in_the_page_skip_2_of_two(db, w1, m1, i1, i2, ix, mk_stock):
    """MIT-GM-27 — the row of a removed item takes no place in the page: skip=2 of two visible rows is empty.
    Rules: `get_by_machine` R5 [BUG-980]"""
    mk_stock(machine_id=m1.id, item_id=ix.id)
    mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MIT-GM-28
@pytest.mark.xfail(
    strict=False,
    reason="BUG-980: A machine's stock list still shows items removed from the catalog "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gm_28__anvil_removed_bolt_active_limit_1_returns_the_bolt_row(db, w1, m1, i1, mk_stock, mk_item):
    """MIT-GM-28 — Anvil removed, Bolt active: limit=1 returns the Bolt row.
    Rules: `get_by_machine` R5 [BUG-980]"""
    ia = mk_item(name="Anvil", name_normalized="anvil", unit="pcs", is_active=False)
    mk_stock(machine_id=m1.id, item_id=ia.id)
    b = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ids(result) == [b.id]


# [claude] MIT-GM-29
def test_mit_gm_29__listing_leaves_the_row_of_a_removed_item_and_the_item_as_they_were(db, w1, m1, i1, ix, mk_stock):
    """MIT-GM-29 — listing leaves the row of a removed item and the item as they were.
    Rules: `get_by_machine` R5a"""
    a = mk_stock(machine_id=m1.id, item_id=ix.id, req_qty=7)
    mk_stock(machine_id=m1.id, item_id=i1.id)
    before = written(db)
    before_a = snap(db, a)
    before_ix = snap(db, ix)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert snap(db, ix) == before_ix
    # Then 4
    assert written(db) == before


# [claude] MIT-GM-30
def test_mit_gm_30__the_row_is_back_unchanged_once_the_item_is_active_again(db, w1, m1, ix, mk_stock):
    """MIT-GM-30 — the row is back, unchanged, once the item is active again.
    Rules: `get_by_machine` R5a"""
    a = mk_stock(machine_id=m1.id, item_id=ix.id, req_qty=7)
    before_a = snap(db, a)
    ix.is_active = True
    db.flush()

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    row = reread(db, a)
    assert row.qty == 5
    assert row.req_qty == 7


# [claude] MIT-GM-31
@pytest.mark.xfail(
    strict=False,
    reason="BUG-976: A machine's stock rows have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gm_31__rows_come_back_by_item_name_case_insensitive(db, w1, m1, mk_stock, mk_item):
    """MIT-GM-31 — rows come back by item name, case-insensitive.
    Rules: `get_by_machine` R6 [BUG-976]"""
    iz = mk_item(name="Zulu", name_normalized="zulu", unit="pcs", is_active=True)
    ia = mk_item(name="apple", name_normalized="apple", unit="pcs", is_active=True)
    ib = mk_item(name="Banana", name_normalized="banana", unit="pcs", is_active=True)
    a = mk_stock(machine_id=m1.id, item_id=iz.id)
    b = mk_stock(machine_id=m1.id, item_id=ia.id)
    c = mk_stock(machine_id=m1.id, item_id=ib.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]
    # Then 2
    assert item_names(result) == ["apple", "Banana", "Zulu"]


# [claude] MIT-GM-32
@pytest.mark.xfail(
    strict=False,
    reason="BUG-976: A machine's stock rows have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gm_32__items_bolt_and_bolt_lower_row_id_first_the_capital_one_holding_it(db, w1, m1, mk_stock, mk_item):
    """MIT-GM-32 — items "Bolt" and "bolt": lower row id first, the capital one holding it.
    Rules: `get_by_machine` R6 [BUG-976]"""
    ib1 = mk_item(name="Bolt", name_normalized="bolt", unit="pcs", is_active=True)
    ib2 = mk_item(name="bolt", name_normalized="bolt", unit="pcs", is_active=True)
    a = mk_stock(machine_id=m1.id, item_id=ib1.id)
    b = mk_stock(machine_id=m1.id, item_id=ib2.id)
    a.qty = 6
    db.flush()

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] MIT-GM-33
@pytest.mark.xfail(
    strict=False,
    reason="BUG-976: A machine's stock rows have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gm_33__items_bolt_and_bolt_lower_row_id_first_the_lower_case_one_holding_it(db, w1, m1, mk_stock, mk_item):
    """MIT-GM-33 — items "Bolt" and "bolt": lower row id first, the lower-case one holding it.
    Rules: `get_by_machine` R6 [BUG-976]"""
    ib1 = mk_item(name="Bolt", name_normalized="bolt", unit="pcs", is_active=True)
    ib2 = mk_item(name="bolt", name_normalized="bolt", unit="pcs", is_active=True)
    a = mk_stock(machine_id=m1.id, item_id=ib2.id)
    b = mk_stock(machine_id=m1.id, item_id=ib1.id)
    a.qty = 6
    db.flush()

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] MIT-GM-34
@pytest.mark.xfail(
    strict=False,
    reason="BUG-976: A machine's stock rows have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gm_34__the_order_is_applied_before_paging_first_window(db, w1, m1, mk_stock, mk_item):
    """MIT-GM-34 — the order is applied before paging: first window.
    Rules: `get_by_machine` R6 [BUG-976], R7"""
    iz = mk_item(name="Zulu", name_normalized="zulu", unit="pcs", is_active=True)
    ia = mk_item(name="apple", name_normalized="apple", unit="pcs", is_active=True)
    ib = mk_item(name="Banana", name_normalized="banana", unit="pcs", is_active=True)
    im = mk_item(name="mango", name_normalized="mango", unit="pcs", is_active=True)
    mk_stock(machine_id=m1.id, item_id=iz.id)
    mk_stock(machine_id=m1.id, item_id=ia.id)
    mk_stock(machine_id=m1.id, item_id=ib.id)
    mk_stock(machine_id=m1.id, item_id=im.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=0, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert item_names(result) == ["apple", "Banana"]


# [claude] MIT-GM-35
@pytest.mark.xfail(
    strict=False,
    reason="BUG-976: A machine's stock rows have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gm_35__the_order_is_applied_before_paging_second_window_no_repeats_and_no_gaps(db, w1, m1, mk_stock, mk_item):
    """MIT-GM-35 — the order is applied before paging: second window, no repeats and no gaps.
    Rules: `get_by_machine` R6 [BUG-976], R7"""
    iz = mk_item(name="Zulu", name_normalized="zulu", unit="pcs", is_active=True)
    ia = mk_item(name="apple", name_normalized="apple", unit="pcs", is_active=True)
    ib = mk_item(name="Banana", name_normalized="banana", unit="pcs", is_active=True)
    im = mk_item(name="mango", name_normalized="mango", unit="pcs", is_active=True)
    mk_stock(machine_id=m1.id, item_id=iz.id)
    mk_stock(machine_id=m1.id, item_id=ia.id)
    mk_stock(machine_id=m1.id, item_id=ib.id)
    mk_stock(machine_id=m1.id, item_id=im.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=2, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert item_names(result) == ["mango", "Zulu"]


# [claude] MIT-GM-36
@pytest.mark.xfail(strict=True, reason="BUG-976: A machine's stock rows have no sort order")
def test_mit_gm_36__the_machine_list_query_asks_for_item_name_case_insensitive_then_row_id(db, w1, m1, i1, mk_stock):
    """MIT-GM-36 — the machine list query asks for item name case-insensitive, then row id.
    Rules: `get_by_machine` R6 [BUG-976]"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)
    [sql] = recorder.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "lower(" in order_part.lower()
    # Then 4
    assert ".name" in order_part
    # Then 5
    assert "machine_items.id" in order_part
    # Then 6
    assert order_part.index(".name") < order_part.index("machine_items.id")
    # Then 7
    assert "DESC" not in order_part


# [claude] MIT-GM-37
def test_mit_gm_37__with_the_default_limit_101_rows_give_exactly_100(db, w1, m1, mk_part_stock):
    """MIT-GM-37 — with the default limit 101 rows give exactly 100.
    Rules: `get_by_machine` R7"""
    all_ids = mk_part_stock(101)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert set(ids(result)) <= set(all_ids)


# [claude] MIT-GM-38
def test_mit_gm_38__with_the_default_limit_100_rows_give_all_100(db, w1, m1, mk_part_stock):
    """MIT-GM-38 — with the default limit 100 rows give all 100.
    Rules: `get_by_machine` R7"""
    all_ids = mk_part_stock(100)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert sorted(ids(result)) == sorted(all_ids)


# [claude] MIT-GM-39
def test_mit_gm_39__an_explicit_limit_of_101_gives_all_101_rows(db, w1, m1, mk_part_stock):
    """MIT-GM-39 — an explicit limit of 101 gives all 101 rows.
    Rules: `get_by_machine` R7"""
    all_ids = mk_part_stock(101)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=101)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert sorted(ids(result)) == sorted(all_ids)


# [claude] MIT-GM-40
def test_mit_gm_40__limit_2_of_three_rows_gives_two_of_them(db, w1, m1, i1, i2, i3, mk_stock):
    """MIT-GM-40 — limit=2 of three rows gives two of them.
    Rules: `get_by_machine` R7"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    c = mk_stock(machine_id=m1.id, item_id=i3.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=2)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert set(ids(result)) <= {a.id, b.id, c.id}


# [claude] MIT-GM-41
def test_mit_gm_41__skip_1_of_three_rows_gives_two_of_them(db, w1, m1, i1, i2, i3, mk_stock):
    """MIT-GM-41 — skip=1 of three rows gives two of them.
    Rules: `get_by_machine` R7"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    c = mk_stock(machine_id=m1.id, item_id=i3.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 2
    # Then 2
    assert set(ids(result)) <= {a.id, b.id, c.id}


# [claude] MIT-GM-42
def test_mit_gm_42__skip_1_and_limit_1_of_three_rows_gives_one_of_them(db, w1, m1, i1, i2, i3, mk_stock):
    """MIT-GM-42 — skip=1 and limit=1 of three rows gives one of them.
    Rules: `get_by_machine` R7"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    c = mk_stock(machine_id=m1.id, item_id=i3.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {a.id, b.id, c.id}


# [claude] MIT-GM-43
def test_mit_gm_43__limit_0_returns_an_empty_list(db, w1, m1, i1, i2, mk_stock):
    """MIT-GM-43 — limit=0 returns an empty list.
    Rules: `get_by_machine` R8"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=0)

    # Then 1
    assert result == []


# [claude] MIT-GM-44
def test_mit_gm_44__limit_1_returns_one_row(db, w1, m1, i1, i2, mk_stock):
    """MIT-GM-44 — limit=1 returns one row.
    Rules: `get_by_machine` R8, R7"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {a.id, b.id}


# [claude] MIT-GM-45
def test_mit_gm_45__skip_equal_to_the_number_of_matching_rows_returns_an_empty_list(db, w1, m1, m2, i1, i2, mk_stock):
    """MIT-GM-45 — skip equal to the number of matching rows returns an empty list.
    Rules: `get_by_machine` R8"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i2.id)
    mk_stock(machine_id=m2.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=2)

    # Then 1
    assert result == []


# [claude] MIT-GM-46
def test_mit_gm_46__skip_past_the_number_of_matching_rows_returns_an_empty_list(db, w1, m1, i1, i2, mk_stock):
    """MIT-GM-46 — skip past the number of matching rows returns an empty list.
    Rules: `get_by_machine` R8"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=3)

    # Then 1
    assert result == []


# [claude] MIT-GM-47
def test_mit_gm_47__skip_one_below_the_number_of_matching_rows_returns_one_row(db, w1, m1, i1, i2, mk_stock):
    """MIT-GM-47 — skip one below the number of matching rows returns one row.
    Rules: `get_by_machine` R8, R7"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id, skip=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {a.id, b.id}


# [claude] MIT-GM-48
def test_mit_gm_48__a_negative_limit_is_rejected_by_postgres(db, w1, m1, i1, mk_stock):
    """MIT-GM-48 — a negative limit is rejected by Postgres.
    Rules: `get_by_machine` R9, Errors row 1"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
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


# [claude] MIT-GM-49
def test_mit_gm_49__a_negative_skip_is_rejected_by_postgres(db, w1, m1, i1, mk_stock):
    """MIT-GM-49 — a negative skip is rejected by Postgres.
    Rules: `get_by_machine` R9, Errors row 2"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
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


# [claude] MIT-GM-50
def test_mit_gm_50__a_row_carries_the_name_and_unit_of_its_item(db, w1, m1, i2, mk_stock):
    """MIT-GM-50 — a row carries the name and unit of its item.
    Rules: `get_by_machine` R11"""
    a = mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].item_name == "Washer"
    # Then 3
    assert result[0].item_unit == "kg"


# [claude] MIT-GM-51
def test_mit_gm_51__reading_a_row_s_item_name_and_unit_needs_no_further_query(db, w1, m1, i1, mk_stock):
    """MIT-GM-51 — reading a row's item name and unit needs no further query.
    Rules: `get_by_machine` R11"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    w1_id = w1.id
    m1_id = m1.id
    db.expire_all()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_machine(db, machine_id=m1_id, workspace_id=w1_id)

        # Then 1
        assert result[0].item_name == "Bolt"
        # Then 2
        assert result[0].item_unit == "pcs"
        # Then 3
        assert len(recorder.selects()) == 1


# [claude] MIT-GM-52
@pytest.mark.xfail(strict=True, reason="BUG-979: A machine's stock list still shows a deleted machine, or a machine of a deleted factory")
def test_mit_gm_52__a_w2_row_on_a_w1_machine_in_a_soft_deleted_factory_is_hidden_too(db, w2, mf, i1, mk_stock):
    """MIT-GM-52 — a W2 row on a W1 machine in a soft-deleted factory is hidden too.
    Rules: `get_by_machine` R4b [BUG-979], R2"""
    mk_stock(machine_id=mf.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=mf.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MIT-GM-53
@pytest.mark.xfail(strict=True, reason="BUG-980: A machine's stock list still shows items removed from the catalog")
def test_mit_gm_53__a_w1_row_of_a_removed_item_of_w2_is_hidden_the_other_row_is_returned(db, w1, w2, m1, i1, mk_stock, mk_item):
    """MIT-GM-53 — a W1 row of a removed item of W2 is hidden, the other row is returned.
    Rules: `get_by_machine` R5 [BUG-980], R2"""
    ir = mk_item(workspace_id=w2.id, name="Far Gasket", name_normalized="far gasket", unit="m", is_active=False)
    mk_stock(machine_id=m1.id, item_id=ir.id)
    b = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [b.id]


# [claude] MIT-GM-54
@pytest.mark.xfail(strict=True, reason="BUG-980: A machine's stock list still shows items removed from the catalog")
def test_mit_gm_54__a_w2_row_of_a_removed_item_of_w1_is_hidden(db, w2, m1, ix, mk_stock):
    """MIT-GM-54 — a W2 row of a removed item of W1 is hidden.
    Rules: `get_by_machine` R5 [BUG-980], R2"""
    mk_stock(machine_id=m1.id, item_id=ix.id, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# --------------------------------------------------------------------------- #
# DAOMachineItem.get_by_machine_and_item
# --------------------------------------------------------------------------- #


# [claude] MIT-GP-01
def test_mit_gp_01__returns_the_session_s_row_of_that_machine_and_item_and_writes_nothing(db, w1, m1, m2, i1, i2, mk_stock):
    """MIT-GP-01 — returns the session's row of that machine and item and writes nothing.
    Rules: `get_by_machine_and_item` R1, Returns, Side effects"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i2.id)
    mk_stock(machine_id=m2.id, item_id=i1.id)
    before = written(db)
    before_a = snap(db, a)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert isinstance(result, MachineItem)
    # Then 3
    assert written(db) == before
    # Then 4
    assert snap(db, a) == before_a


# [claude] MIT-GP-02
def test_mit_gp_02__the_same_machine_with_another_item_is_not_matched(db, w1, m1, i1, i2, mk_stock):
    """MIT-GP-02 — the same machine with another item is not matched.
    Rules: `get_by_machine_and_item` R2"""
    mk_stock(machine_id=m1.id, item_id=i2.id)
    before = written(db)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before


# [claude] MIT-GP-03
def test_mit_gp_03__the_same_item_on_another_machine_is_not_matched(db, w1, m1, m2, i1, mk_stock):
    """MIT-GP-03 — the same item on another machine is not matched.
    Rules: `get_by_machine_and_item` R2"""
    mk_stock(machine_id=m2.id, item_id=i1.id)
    before = written(db)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before


# [claude] MIT-GP-04
def test_mit_gp_04__the_same_pair_in_another_workspace_is_not_matched(db, w1, w2, m1, i1, mk_stock):
    """MIT-GP-04 — the same pair in another workspace is not matched.
    Rules: `get_by_machine_and_item` R2"""
    z = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)
    before = written(db)
    before_z = snap(db, z)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, z) == before_z


# [claude] MIT-GP-05
def test_mit_gp_05__the_same_pair_in_two_workspaces_w1_finds_its_own_row(db, w1, w2, m1, i1, mk_stock):
    """MIT-GP-05 — the same pair in two workspaces: W1 finds its own row.
    Rules: `get_by_machine_and_item` R2"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is a


# [claude] MIT-GP-06
def test_mit_gp_06__the_same_pair_in_two_workspaces_w2_finds_its_own_row(db, w2, m1, i1, mk_stock):
    """MIT-GP-06 — the same pair in two workspaces: W2 finds its own row.
    Rules: `get_by_machine_and_item` R2"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    z = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert result is z


# [claude] MIT-GP-07
def test_mit_gp_07__machine_id_0_returns_none_and_creates_nothing(db, w1, m1, i1, mk_stock):
    """MIT-GP-07 — machine_id=0 returns None and creates nothing.
    Rules: `get_by_machine_and_item` R3"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    before = written(db)

    result = dao.get_by_machine_and_item(db, machine_id=0, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before


# [claude] MIT-GP-08
def test_mit_gp_08__item_id_0_returns_none_and_creates_nothing(db, w1, m1, i1, mk_stock):
    """MIT-GP-08 — item_id=0 returns None and creates nothing.
    Rules: `get_by_machine_and_item` R3"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    before = written(db)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=0, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before


# [claude] MIT-GP-09
def test_mit_gp_09__an_unknown_machine_id_returns_none_and_creates_nothing(db, w1, m1, i1, mk_stock):
    """MIT-GP-09 — an unknown machine id returns None and creates nothing.
    Rules: `get_by_machine_and_item` R3"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    before = written(db)

    result = dao.get_by_machine_and_item(db, machine_id=MISSING, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before


# [claude] MIT-GP-10
def test_mit_gp_10__an_unknown_item_id_returns_none_and_creates_nothing(db, w1, m1, i1, mk_stock):
    """MIT-GP-10 — an unknown item id returns None and creates nothing.
    Rules: `get_by_machine_and_item` R3"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    before = written(db)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before


# [claude] MIT-GP-11
def test_mit_gp_11__an_unknown_workspace_returns_none_and_creates_nothing(db, m1, i1, mk_stock):
    """MIT-GP-11 — an unknown workspace returns None and creates nothing.
    Rules: `get_by_machine_and_item` R3"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    before = written(db)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=MISSING)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before


# [claude] MIT-GP-12
def test_mit_gp_12__no_stock_row_at_all_none_and_no_row_is_created(db, w1, m1, i1):
    """MIT-GP-12 — no stock row at all: None, and no row is created.
    Rules: `get_by_machine_and_item` R3"""
    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    assert count_rows(db) == 0


# [claude] MIT-GP-13
def test_mit_gp_13__the_row_of_a_soft_deleted_machine_is_found(db, w1, md, i1, mk_stock):
    """MIT-GP-13 — the row of a soft-deleted machine is found.
    Rules: `get_by_machine_and_item` R4"""
    a = mk_stock(machine_id=md.id, item_id=i1.id)
    before_a = snap(db, a)

    result = dao.get_by_machine_and_item(db, machine_id=md.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIT-GP-14
def test_mit_gp_14__the_row_of_a_machine_in_a_soft_deleted_factory_is_found(db, w1, mf, i1, mk_stock):
    """MIT-GP-14 — the row of a machine in a soft-deleted factory is found.
    Rules: `get_by_machine_and_item` R4"""
    a = mk_stock(machine_id=mf.id, item_id=i1.id)
    before_a = snap(db, a)

    result = dao.get_by_machine_and_item(db, machine_id=mf.id, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert snap(db, a) == before_a


# [claude] MIT-GP-15
def test_mit_gp_15__the_row_of_a_removed_item_is_found(db, w1, m1, ix, mk_stock):
    """MIT-GP-15 — the row of a removed item is found.
    Rules: `get_by_machine_and_item` R4"""
    a = mk_stock(machine_id=m1.id, item_id=ix.id)
    before_a = snap(db, a)

    result = dao.get_by_machine_and_item(db, machine_id=m1.id, item_id=ix.id, workspace_id=w1.id)

    # Then 1
    assert result is a
    # Then 2
    assert snap(db, a) == before_a

# --------------------------------------------------------------------------- #
# DAOMachineItem.get_by_item
# --------------------------------------------------------------------------- #


# [claude] MIT-GT-01
def test_mit_gt_01__returns_a_list_of_the_item_s_rows_and_writes_nothing(db, w1, m1, m2, i1, i2, mk_stock):
    """MIT-GT-01 — returns a list of the item's rows and writes nothing.
    Rules: `get_by_item` R1, Returns, Side effects"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m2.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i2.id)
    before = written(db)
    before_a = snap(db, a)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 3
    assert isinstance(result[0], MachineItem)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a) == before_a


# [claude] MIT-GT-02
def test_mit_gt_02__the_other_item_gets_only_its_own_row(db, w1, m1, m2, i1, i2, mk_stock):
    """MIT-GT-02 — the other item gets only its own row.
    Rules: `get_by_item` R1"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m2.id, item_id=i1.id)
    c = mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_item(db, item_id=i2.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [c.id]


# [claude] MIT-GT-03
def test_mit_gt_03__rows_are_returned_whatever_their_quantities(db, w1, m1, m2, m3, i1, mk_stock):
    """MIT-GT-03 — rows are returned whatever their quantities.
    Rules: `get_by_item` R1"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id, qty=0)
    b = mk_stock(machine_id=m2.id, item_id=i1.id, qty=-4)
    c = mk_stock(machine_id=m3.id, item_id=i1.id, qty=3, req_qty=9, defective_qty=1)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id, c.id]


# [claude] MIT-GT-04
def test_mit_gt_04__the_right_item_under_another_workspace_returns_an_empty_list(db, w2, m1, i1, mk_stock):
    """MIT-GT-04 — the right item under another workspace returns an empty list.
    Rules: `get_by_item` R2"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MIT-GT-05
def test_mit_gt_05__a_w2_row_of_an_item_of_w1_is_returned_for_w2(db, w2, m1, i1, mk_stock):
    """MIT-GT-05 — a W2 row of an item of W1 is returned for W2.
    Rules: `get_by_item` R2"""
    z = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [z.id]


# [claude] MIT-GT-06
def test_mit_gt_06__a_w2_row_of_an_item_of_w1_is_not_returned_for_w1(db, w1, w2, m1, i1, mk_stock):
    """MIT-GT-06 — a W2 row of an item of W1 is not returned for W1.
    Rules: `get_by_item` R2"""
    mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GT-07
def test_mit_gt_07__the_same_machine_and_item_in_two_workspaces_w1_gets_only_its_own_row(db, w1, w2, m1, i1, mk_stock):
    """MIT-GT-07 — the same machine and item in two workspaces: W1 gets only its own row.
    Rules: `get_by_item` R2"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MIT-GT-08
def test_mit_gt_08__the_same_machine_and_item_in_two_workspaces_w2_gets_only_its_own_row(db, w2, m1, i1, mk_stock):
    """MIT-GT-08 — the same machine and item in two workspaces: W2 gets only its own row.
    Rules: `get_by_item` R2"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    z = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [z.id]


# [claude] MIT-GT-09
def test_mit_gt_09__a_w1_row_of_an_item_of_w2_is_returned_for_w1(db, w1, m1, i9, mk_stock):
    """MIT-GT-09 — a W1 row of an item of W2 is returned for W1.
    Rules: `get_by_item` R2"""
    a = mk_stock(machine_id=m1.id, item_id=i9.id)

    result = dao.get_by_item(db, item_id=i9.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] MIT-GT-10
def test_mit_gt_10__an_unknown_item_id_returns_an_empty_list(db, w1, m1, i1, mk_stock):
    """MIT-GT-10 — an unknown item id returns an empty list.
    Rules: `get_by_item` R3"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_item(db, item_id=MISSING, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GT-11
def test_mit_gt_11__item_id_0_returns_an_empty_list(db, w1, m1, i1, mk_stock):
    """MIT-GT-11 — item_id=0 returns an empty list.
    Rules: `get_by_item` R3"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_item(db, item_id=0, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GT-12
def test_mit_gt_12__an_item_with_no_rows_returns_an_empty_list(db, w1, m1, i1, i2, mk_stock):
    """MIT-GT-12 — an item with no rows returns an empty list.
    Rules: `get_by_item` R3"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_item(db, item_id=i2.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GT-13
@pytest.mark.xfail(strict=True, reason="BUG-981: Item summary still lists and counts placements on deleted machines and in deleted factories")
def test_mit_gt_13__on_a_live_and_on_a_soft_deleted_machine_only_the_live_machine_s_row(db, w1, m1, md, i1, mk_stock):
    """MIT-GT-13 — on a live and on a soft-deleted machine: only the live machine's row.
    Rules: `get_by_item` R3a [BUG-981]"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=md.id, item_id=i1.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] MIT-GT-14
@pytest.mark.xfail(strict=True, reason="BUG-981: Item summary still lists and counts placements on deleted machines and in deleted factories")
def test_mit_gt_14__only_on_a_soft_deleted_machine_an_empty_list(db, w1, md, i1, mk_stock):
    """MIT-GT-14 — only on a soft-deleted machine: an empty list.
    Rules: `get_by_item` R3a [BUG-981]"""
    mk_stock(machine_id=md.id, item_id=i1.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GT-15
@pytest.mark.xfail(strict=True, reason="BUG-981: Item summary still lists and counts placements on deleted machines and in deleted factories")
def test_mit_gt_15__a_w2_row_on_a_soft_deleted_machine_of_w1_is_hidden_too(db, w2, md, i1, mk_stock):
    """MIT-GT-15 — a W2 row on a soft-deleted machine of W1 is hidden too.
    Rules: `get_by_item` R3a [BUG-981], R2"""
    mk_stock(machine_id=md.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MIT-GT-16
@pytest.mark.xfail(strict=True, reason="BUG-981: Item summary still lists and counts placements on deleted machines and in deleted factories")
def test_mit_gt_16__on_a_live_machine_and_on_one_in_a_soft_deleted_factory_only_the_first(db, w1, m1, mf, i1, mk_stock):
    """MIT-GT-16 — on a live machine and on one in a soft-deleted factory: only the first row.
    Rules: `get_by_item` R3b [BUG-981]"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    mk_stock(machine_id=mf.id, item_id=i1.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id]


# [claude] MIT-GT-17
@pytest.mark.xfail(strict=True, reason="BUG-981: Item summary still lists and counts placements on deleted machines and in deleted factories")
def test_mit_gt_17__only_on_a_machine_in_a_soft_deleted_factory_an_empty_list(db, w1, mf, i1, mk_stock):
    """MIT-GT-17 — only on a machine in a soft-deleted factory: an empty list.
    Rules: `get_by_item` R3b [BUG-981]"""
    mk_stock(machine_id=mf.id, item_id=i1.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == []


# [claude] MIT-GT-18
def test_mit_gt_18__the_rows_of_a_soft_deleted_machine_stay_as_they_were(db, w1, md, i1, mk_stock):
    """MIT-GT-18 — the rows of a soft-deleted machine stay as they were.
    Rules: `get_by_item` R3c"""
    b = mk_stock(machine_id=md.id, item_id=i1.id, req_qty=7, defective_qty=1)
    before = written(db)
    before_b = snap(db, b)
    before_md = snap(db, md)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert snap(db, b) == before_b
    # Then 3
    assert snap(db, md) == before_md
    # Then 4
    assert written(db) == before


# [claude] MIT-GT-19
def test_mit_gt_19__the_rows_of_a_machine_in_a_soft_deleted_factory_stay_as_they_were(db, w1, fd, mf, i1, mk_stock):
    """MIT-GT-19 — the rows of a machine in a soft-deleted factory stay as they were.
    Rules: `get_by_item` R3c"""
    b = mk_stock(machine_id=mf.id, item_id=i1.id, req_qty=7, defective_qty=1)
    before = written(db)
    before_b = snap(db, b)
    before_mf = snap(db, mf)
    before_fd = snap(db, fd)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert snap(db, b) == before_b
    # Then 3
    assert snap(db, mf) == before_mf
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    assert written(db) == before


# [claude] MIT-GT-20
def test_mit_gt_20__an_inactive_but_live_machine_hides_nothing(db, w1, m1, mi, i1, mk_stock):
    """MIT-GT-20 — an inactive but live machine hides nothing.
    Rules: `get_by_item` R3c"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=mi.id, item_id=i1.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MIT-GT-21
def test_mit_gt_21__a_live_machine_in_an_inactive_but_live_factory_hides_nothing(db, w1, m1, mg, i1, mk_stock):
    """MIT-GT-21 — a live machine in an inactive but live factory hides nothing.
    Rules: `get_by_item` R3c"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=mg.id, item_id=i1.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]


# [claude] MIT-GT-22
def test_mit_gt_22__the_row_is_back_unchanged_once_the_machine_is_no_longer_deleted(db, w1, md, i1, mk_stock):
    """MIT-GT-22 — the row is back, unchanged, once the machine is no longer deleted.
    Rules: `get_by_item` R3c"""
    b = mk_stock(machine_id=md.id, item_id=i1.id, req_qty=7)
    before_b = snap(db, b)
    md.is_deleted = False
    md.is_active = True
    db.flush()

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id]
    # Then 2
    assert snap(db, b) == before_b
    # Then 3
    row = reread(db, b)
    assert row.qty == 5
    assert row.req_qty == 7


# [claude] MIT-GT-23
def test_mit_gt_23__the_row_is_back_unchanged_once_the_factory_is_no_longer_deleted(db, w1, fd, mf, i1, mk_stock):
    """MIT-GT-23 — the row is back, unchanged, once the factory is no longer deleted.
    Rules: `get_by_item` R3c"""
    b = mk_stock(machine_id=mf.id, item_id=i1.id, req_qty=7)
    before_b = snap(db, b)
    fd.is_deleted = False
    db.flush()

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [b.id]
    # Then 2
    assert snap(db, b) == before_b
    # Then 3
    row = reread(db, b)
    assert row.qty == 5
    assert row.req_qty == 7


# [claude] MIT-GT-24
def test_mit_gt_24__a_removed_item_s_rows_are_returned_like_any_other(db, w1, m1, m2, ix, mk_stock):
    """MIT-GT-24 — a removed item's rows are returned like any other.
    Rules: `get_by_item` R4"""
    a = mk_stock(machine_id=m1.id, item_id=ix.id)
    b = mk_stock(machine_id=m2.id, item_id=ix.id)
    before_a = snap(db, a)
    before_ix = snap(db, ix)

    result = dao.get_by_item(db, item_id=ix.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert snap(db, ix) == before_ix


# [claude] MIT-GT-25
@pytest.mark.xfail(strict=True, reason="BUG-982: Item summary silently stops at 500 machines")
def test_mit_gt_25__501_machines_holding_the_item_all_501_rows(db, w1, i1, mk_press_stock):
    """MIT-GT-25 — 501 machines holding the item: all 501 rows.
    Rules: `get_by_item` R5 [BUG-982]"""
    all_ids = mk_press_stock(501)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 501
    # Then 2
    assert sorted(ids(result)) == sorted(all_ids)


# [claude] MIT-GT-26
def test_mit_gt_26__500_machines_holding_the_item_all_500_rows(db, w1, i1, mk_press_stock):
    """MIT-GT-26 — 500 machines holding the item: all 500 rows.
    Rules: `get_by_item` R5"""
    all_ids = mk_press_stock(500)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert len(result) == 500
    # Then 2
    assert sorted(ids(result)) == sorted(all_ids)


# [claude] MIT-GT-27
@pytest.mark.xfail(
    strict=False,
    reason="BUG-977: Machine placements of an item have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gt_27__rows_come_back_in_id_order(db, w1, m1, m2, i1, mk_stock):
    """MIT-GT-27 — rows come back in id order.
    Rules: `get_by_item` R6 [BUG-977]"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m2.id, item_id=i1.id)
    a.qty = 6
    db.flush()

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] MIT-GT-28
@pytest.mark.xfail(strict=True, reason="BUG-977: Machine placements of an item have no sort order")
def test_mit_gt_28__the_item_query_asks_the_database_for_id_order(db, w1, m1, i1, mk_stock):
    """MIT-GT-28 — the item query asks the database for id order.
    Rules: `get_by_item` R6 [BUG-977]"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)
    [sql] = recorder.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_items.id" in order_part
    # Then 4
    assert "DESC" not in order_part


# [claude] MIT-GT-29
def test_mit_gt_29__a_row_carries_the_name_and_unit_of_its_item(db, w1, m1, i2, mk_stock):
    """MIT-GT-29 — a row carries the name and unit of its item.
    Rules: `get_by_item` R7"""
    a = mk_stock(machine_id=m1.id, item_id=i2.id)

    result = dao.get_by_item(db, item_id=i2.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].item_name == "Washer"
    # Then 3
    assert result[0].item_unit == "kg"


# [claude] MIT-GT-30
def test_mit_gt_30__a_row_of_a_removed_item_carries_that_item_s_name_and_unit(db, w1, m1, ix, mk_stock):
    """MIT-GT-30 — a row of a removed item carries that item's name and unit.
    Rules: `get_by_item` R7"""
    a = mk_stock(machine_id=m1.id, item_id=ix.id)

    result = dao.get_by_item(db, item_id=ix.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert result[0].item_name == "Old Gasket"
    # Then 3
    assert result[0].item_unit == "m"


# [claude] MIT-GT-31
def test_mit_gt_31__reading_a_row_s_item_name_and_unit_needs_no_further_query(db, w1, m1, i1, mk_stock):
    """MIT-GT-31 — reading a row's item name and unit needs no further query.
    Rules: `get_by_item` R7"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    w1_id = w1.id
    i1_id = i1.id
    db.expire_all()

    with StatementRecorder(db) as recorder:
        result = dao.get_by_item(db, item_id=i1_id, workspace_id=w1_id)

        # Then 1
        assert result[0].item_name == "Bolt"
        # Then 2
        assert result[0].item_unit == "pcs"
        # Then 3
        assert len(recorder.selects()) == 1


# [claude] MIT-GT-32
@pytest.mark.xfail(strict=True, reason="BUG-982: Item summary silently stops at 500 machines")
def test_mit_gt_32__the_item_query_carries_no_limit_and_no_offset_so_no_cap_of_any_size(db, w1, m1, i1, mk_stock):
    """MIT-GT-32 — the item query carries no LIMIT and no OFFSET, so no cap of any size exists.
    Rules: `get_by_item` R5 [BUG-982]"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    with StatementRecorder(db) as recorder:
        result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)
    [sql] = recorder.selects()

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "LIMIT" not in sql
    # Then 3
    assert "OFFSET" not in sql


# [claude] MIT-GT-33
@pytest.mark.xfail(strict=True, reason="BUG-981: Item summary still lists and counts placements on deleted machines and in deleted factories")
def test_mit_gt_33__a_w2_row_on_a_w1_machine_in_a_soft_deleted_factory_is_hidden_too(db, w2, mf, i1, mk_stock):
    """MIT-GT-33 — a W2 row on a W1 machine in a soft-deleted factory is hidden too.
    Rules: `get_by_item` R3b [BUG-981], R2"""
    mk_stock(machine_id=mf.id, item_id=i1.id, workspace_id=w2.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w2.id)

    # Then 1
    assert result == []


# [claude] MIT-GT-34
@pytest.mark.xfail(
    strict=False,
    reason="BUG-977: Machine placements of an item have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_gt_34__id_order_holds_when_the_lower_id_sits_on_the_higher_machine(db, w1, m1, m2, i1, mk_stock):
    """MIT-GT-34 — id order holds when the lower id sits on the higher machine.
    Rules: `get_by_item` R6 [BUG-977]"""
    a = mk_stock(machine_id=m2.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_by_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert ids(result) == [a.id, b.id]


# --------------------------------------------------------------------------- #
# Inherited BaseDAO methods on MachineItem
# --------------------------------------------------------------------------- #


# [claude] MIT-INH-01
def test_mit_inh_01__create_with_a_dict_stores_a_row_with_the_defaults_and_writes_no_ledger(db, w1, m1, i1):
    """MIT-INH-01 — create with a dict stores a row with the defaults and writes no ledger row.
    Rules: `inherited` R1, Side effects"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    # Then 3
    assert row.qty == 0
    assert row.req_qty is None
    assert row.defective_qty is None
    # Then 4
    assert count_rows(db) == 1
    # Then 5
    assert db.scalar(text("select count(*) from machine_item_ledger")) == 0


# [claude] MIT-INH-02
def test_mit_inh_02__create_with_qty_none_gives_0(db, w1, m1, i1):
    """MIT-INH-02 — create with qty=None gives 0.
    Rules: `inherited` R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "qty": None})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 0


# [claude] MIT-INH-03
def test_mit_inh_03__create_is_flushed_not_committed_a_rollback_removes_the_row(db, w1, m1, i1):
    """MIT-INH-03 — create is flushed, not committed: a rollback removes the row.
    Rules: `inherited` R1, Overview (never commits)"""
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id})

        # Then 1
        assert result.id is not None
        # Then 2
        assert count_rows(db) == 1
        # Then 3
        sp.rollback()
        assert count_rows(db) == 0
        # Then 4
        assert commit_spy.call_count == 0


# [claude] MIT-INH-04
def test_mit_inh_04__create_with_a_machineitemcreate_fails_on_flush_and_saves_nothing(db, m1, i1):
    """MIT-INH-04 — create with a MachineItemCreate fails on flush and saves nothing.
    Rules: `inherited` R2, Errors row 1"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in=MachineItemCreate(machine_id=m1.id, item_id=i1.id))
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23502"
    # Then 4
    assert 'column "workspace_id"' in str(exc.value.orig)
    # Then 5
    assert count_rows(db) == 0


# [claude] MIT-INH-05
def test_mit_inh_05__create_with_a_dict_without_workspace_id_fails_on_flush_and_saves_nothing(db, m1, i1):
    """MIT-INH-05 — create with a dict without workspace_id fails on flush and saves nothing.
    Rules: `inherited` R2, Errors row 1"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"machine_id": m1.id, "item_id": i1.id})
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "workspace_id"' in str(exc.value.orig)
    # Then 4
    assert count_rows(db) == 0


# [claude] MIT-INH-06
def test_mit_inh_06__create_with_an_unknown_machine_id_fails_on_flush_and_saves_nothing(db, w1, i1):
    """MIT-INH-06 — create with an unknown machine_id fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": MISSING, "item_id": i1.id})
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert "machine_items_machine_id_fkey" in str(exc.value.orig)
    # Then 5
    assert count_rows(db) == 0


# [claude] MIT-INH-07
def test_mit_inh_07__create_with_an_unknown_item_id_fails_on_flush_and_saves_nothing(db, w1, m1):
    """MIT-INH-07 — create with an unknown item_id fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": MISSING})
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert "machine_items_item_id_fkey" in str(exc.value.orig)
    # Then 5
    assert count_rows(db) == 0


# [claude] MIT-INH-08
def test_mit_inh_08__create_with_an_unknown_workspace_id_fails_on_flush_and_saves_nothing(db, m1, i1):
    """MIT-INH-08 — create with an unknown workspace_id fails on flush and saves nothing.
    Rules: `inherited` R3, Errors row 2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": MISSING, "machine_id": m1.id, "item_id": i1.id})
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23503"
    # Then 4
    assert "machine_items_workspace_id_fkey" in str(exc.value.orig)
    # Then 5
    assert count_rows(db) == 0


# [claude] MIT-INH-09
def test_mit_inh_09__create_with_a_key_that_is_no_attribute_of_the_model_raises_typeerror(db, w1, m1, i1):
    """MIT-INH-09 — create with a key that is no attribute of the model raises TypeError and adds nothing.
    Rules: `inherited` R3, Errors row 4"""
    # Then 1
    with pytest.raises(TypeError):
        dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "avg_price": 5})
    # Then 2
    assert count_rows(db) == 0
    # Then 3
    assert len(db.new) == 0


# [claude] MIT-INH-10
@pytest.mark.xfail(strict=True, reason="BUG-983: Machine stock can hold two rows for the same machine and item")
def test_mit_inh_10__a_second_row_for_a_taken_key_is_refused_and_the_first_row_stays(db, w1, m1, i1, mk_stock):
    """MIT-INH-10 — a second row for a taken key is refused and the first row stays.
    Rules: `inherited` R4 [BUG-983], Errors row 5"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id, req_qty=7, defective_qty=1)
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "qty": 9})
    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23505"
    # Then 4
    assert count_rows(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id) == 1
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    row = reread(db, a)
    assert row.qty == 5
    assert row.req_qty == 7
    assert row.defective_qty == 1


# [claude] MIT-INH-11
@pytest.mark.xfail(strict=True, reason="BUG-983: Machine stock can hold two rows for the same machine and item")
def test_mit_inh_11__a_taken_key_of_w2_is_refused_while_w1_holds_the_same_pair(db, w1, w2, m1, i1, mk_stock):
    """MIT-INH-11 — a taken key of W2 is refused while W1 holds the same pair.
    Rules: `inherited` R4 [BUG-983], Errors row 5"""
    mk_stock(machine_id=m1.id, item_id=i1.id)
    z = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)
    before_z = snap(db, z)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w2.id, "machine_id": m1.id, "item_id": i1.id})
    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23505"
    # Then 4
    assert count_rows(db, workspace_id=w2.id, machine_id=m1.id, item_id=i1.id) == 1
    # Then 5
    assert count_rows(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id) == 1
    # Then 6
    assert snap(db, z) == before_z


# [claude] MIT-INH-12
@pytest.mark.xfail(strict=True, reason="BUG-983: Machine stock can hold two rows for the same machine and item")
def test_mit_inh_12__update_moving_a_row_onto_a_taken_key_by_its_machine_is_refused(db, w1, m1, m2, i1, mk_stock):
    """MIT-INH-12 — update moving a row onto a taken key by its machine is refused.
    Rules: `inherited` R4a [BUG-983], Errors row 5"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m2.id, item_id=i1.id, qty=3)
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.update(db, db_obj=b, obj_in={"machine_id": m1.id})
    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23505"
    # Then 4
    db.refresh(b)
    assert b.machine_id == m2.id
    assert b.item_id == i1.id
    assert b.workspace_id == w1.id
    assert b.qty == 3
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert count_rows(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id) == 1


# [claude] MIT-INH-13
@pytest.mark.xfail(strict=True, reason="BUG-983: Machine stock can hold two rows for the same machine and item")
def test_mit_inh_13__update_moving_a_row_onto_a_taken_key_by_its_item_is_refused(db, w1, m1, i1, i2, mk_stock):
    """MIT-INH-13 — update moving a row onto a taken key by its item is refused.
    Rules: `inherited` R4a [BUG-983], Errors row 5"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id, qty=3)
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.update(db, db_obj=b, obj_in={"item_id": i1.id})
    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23505"
    # Then 4
    db.refresh(b)
    assert b.machine_id == m1.id
    assert b.item_id == i2.id
    assert b.workspace_id == w1.id
    assert b.qty == 3
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert count_rows(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id) == 1


# [claude] MIT-INH-14
@pytest.mark.xfail(strict=True, reason="BUG-983: Machine stock can hold two rows for the same machine and item")
def test_mit_inh_14__update_moving_a_row_onto_a_taken_key_by_its_workspace_is_refused(db, w1, w2, m1, i1, mk_stock):
    """MIT-INH-14 — update moving a row onto a taken key by its workspace is refused.
    Rules: `inherited` R4a [BUG-983], Errors row 5"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    z = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id, qty=3)
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.update(db, db_obj=z, obj_in={"workspace_id": w1.id})
    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert exc.value.orig.pgcode == "23505"
    # Then 4
    db.refresh(z)
    assert z.machine_id == m1.id
    assert z.item_id == i1.id
    assert z.workspace_id == w2.id
    assert z.qty == 3
    # Then 5
    assert snap(db, a) == before_a
    # Then 6
    assert count_rows(db, workspace_id=w1.id, machine_id=m1.id, item_id=i1.id) == 1


# [claude] MIT-INH-15
def test_mit_inh_15__the_same_item_on_another_machine_stays_allowed(db, w1, m1, m2, i1, mk_stock):
    """MIT-INH-15 — the same item on another machine stays allowed.
    Rules: `inherited` R4b"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m2.id, "item_id": i1.id})

    # Then 1
    assert result.id != a.id
    # Then 2
    assert count_rows(db) == 2
    # Then 3
    assert snap(db, a) == before_a


# [claude] MIT-INH-16
def test_mit_inh_16__another_item_on_the_same_machine_stays_allowed(db, w1, m1, i1, i2, mk_stock):
    """MIT-INH-16 — another item on the same machine stays allowed.
    Rules: `inherited` R4b"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i2.id})

    # Then 1
    assert result.id != a.id
    # Then 2
    assert count_rows(db) == 2
    # Then 3
    assert snap(db, a) == before_a


# [claude] MIT-INH-17
def test_mit_inh_17__the_same_machine_and_item_under_w2_stay_allowed_while_w1_holds_them(db, w2, m1, i1, mk_stock):
    """MIT-INH-17 — the same machine and item under W2 stay allowed while W1 holds them.
    Rules: `inherited` R4b, R6"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    before_a = snap(db, a)

    result = dao.create(db, obj_in={"workspace_id": w2.id, "machine_id": m1.id, "item_id": i1.id})

    # Then 1
    assert result.id != a.id
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    # Then 3
    assert count_rows(db) == 2
    # Then 4
    assert snap(db, a) == before_a


# [claude] MIT-INH-18
def test_mit_inh_18__the_same_machine_and_item_under_w1_stay_allowed_while_w2_holds_them(db, w1, w2, m1, i1, mk_stock):
    """MIT-INH-18 — the same machine and item under W1 stay allowed while W2 holds them.
    Rules: `inherited` R4b, R6"""
    z = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w2.id)
    before_z = snap(db, z)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id})

    # Then 1
    assert result.id != z.id
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    # Then 3
    assert count_rows(db) == 2
    # Then 4
    assert snap(db, z) == before_z


# [claude] MIT-INH-19
def test_mit_inh_19__update_onto_a_pair_w1_holds_stays_allowed_when_the_row_moves_to_w2(db, w2, m1, m2, i1, mk_stock):
    """MIT-INH-19 — update onto a pair W1 holds stays allowed when the row moves to W2.
    Rules: `inherited` R4b, R8"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m2.id, item_id=i1.id)
    before_a = snap(db, a)

    result = dao.update(db, db_obj=b, obj_in={"workspace_id": w2.id, "machine_id": m1.id})

    # Then 1
    assert result is b
    # Then 2
    row = reread(db, b)
    assert row.workspace_id == w2.id
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    # Then 3
    assert snap(db, a) == before_a


# [claude] MIT-INH-20
def test_mit_inh_20__update_naming_the_row_s_own_key_stays_allowed(db, w1, m1, i1, mk_stock):
    """MIT-INH-20 — update naming the row's own key stays allowed.
    Rules: `inherited` R4b, R8"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.update(db, db_obj=a, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "qty": 9})

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    assert row.qty == 9
    # Then 3
    assert count_rows(db) == 1


# [claude] MIT-INH-21
def test_mit_inh_21__negative_quantities_are_stored(db, w1, m1, i1):
    """MIT-INH-21 — negative quantities are stored.
    Rules: `inherited` R5"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "qty": -4, "req_qty": -4, "defective_qty": -4})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == -4
    assert row.req_qty == -4
    assert row.defective_qty == -4


# [claude] MIT-INH-22
def test_mit_inh_22__qty_of_2147483648_is_outside_the_32_bit_range_and_nothing_is_saved(db, w1, m1, i1):
    """MIT-INH-22 — qty of 2147483648 is outside the 32-bit range and nothing is saved.
    Rules: `inherited` R5, Errors row 3"""
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "qty": 2147483648})
    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert count_rows(db) == 0


# [claude] MIT-INH-23
def test_mit_inh_23__req_qty_of_2147483648_is_outside_the_32_bit_range_and_nothing_is_saved(db, w1, m1, i1):
    """MIT-INH-23 — req_qty of 2147483648 is outside the 32-bit range and nothing is saved.
    Rules: `inherited` R5, Errors row 3"""
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "req_qty": 2147483648})
    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert count_rows(db) == 0


# [claude] MIT-INH-24
def test_mit_inh_24__defective_qty_of_2147483648_is_outside_the_32_bit_range_and_nothing_is(db, w1, m1, i1):
    """MIT-INH-24 — defective_qty of 2147483648 is outside the 32-bit range and nothing is saved.
    Rules: `inherited` R5, Errors row 3"""
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "defective_qty": 2147483648})
    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert count_rows(db) == 0


# [claude] MIT-INH-25
def test_mit_inh_25__qty_of_2147483649_is_outside_the_32_bit_range_and_nothing_is_saved(db, w1, m1, i1):
    """MIT-INH-25 — qty of -2147483649 is outside the 32-bit range and nothing is saved.
    Rules: `inherited` R5, Errors row 3"""
    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "qty": -2147483649})
    # Then 2
    assert isinstance(exc.value.orig, NumericValueOutOfRange)
    # Then 3
    assert exc.value.orig.pgcode == "22003"
    # Then 4
    assert count_rows(db) == 0


# [claude] MIT-INH-26
def test_mit_inh_26__the_32_bit_maximum_is_stored_in_all_three_quantities(db, w1, m1, i1):
    """MIT-INH-26 — the 32-bit maximum is stored in all three quantities.
    Rules: `inherited` R5"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "qty": 2147483647, "req_qty": 2147483647, "defective_qty": 2147483647})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == 2147483647
    assert row.req_qty == 2147483647
    assert row.defective_qty == 2147483647


# [claude] MIT-INH-27
def test_mit_inh_27__the_32_bit_minimum_is_stored_in_all_three_quantities(db, w1, m1, i1):
    """MIT-INH-27 — the 32-bit minimum is stored in all three quantities.
    Rules: `inherited` R5"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i1.id, "qty": -2147483648, "req_qty": -2147483648, "defective_qty": -2147483648})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.qty == -2147483648
    assert row.req_qty == -2147483648
    assert row.defective_qty == -2147483648


# [claude] MIT-INH-28
def test_mit_inh_28__create_saves_a_row_for_a_soft_deleted_machine(db, w1, md, i1):
    """MIT-INH-28 — create saves a row for a soft-deleted machine.
    Rules: `inherited` R6"""
    before_md = snap(db, md)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": md.id, "item_id": i1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.machine_id == md.id
    # Then 3
    assert snap(db, md) == before_md


# [claude] MIT-INH-29
def test_mit_inh_29__create_saves_a_row_for_a_removed_item(db, w1, m1, ix):
    """MIT-INH-29 — create saves a row for a removed item.
    Rules: `inherited` R6"""
    before_ix = snap(db, ix)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": ix.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.item_id == ix.id
    # Then 3
    assert snap(db, ix) == before_ix


# [claude] MIT-INH-30
def test_mit_inh_30__create_saves_a_row_for_an_item_of_another_workspace_and_item_name_gives(db, w1, m1, i9):
    """MIT-INH-30 — create saves a row for an item of another workspace, and item_name gives that item's name.
    Rules: `inherited` R6"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "item_id": i9.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.item_id == i9.id
    # Then 3
    assert row.item_name == "Far Crate"


# [claude] MIT-INH-31
def test_mit_inh_31__update_with_a_machineitemupdate_applies_qty_and_keeps_fields_sent_as(db, w1, m1, i1, mk_stock):
    """MIT-INH-31 — update with a MachineItemUpdate applies qty and keeps fields sent as None.
    Rules: `inherited` R7, Side effects"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id, qty=5, req_qty=7, defective_qty=1)

    result = dao.update(db, db_obj=a, obj_in=MachineItemUpdate(qty=6, req_qty=None))

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.qty == 6
    assert row.req_qty == 7
    assert row.defective_qty == 1
    # Then 3
    assert row.machine_id == m1.id
    assert row.item_id == i1.id
    assert row.workspace_id == w1.id
    # Then 4
    assert db.scalar(text("select count(*) from machine_item_ledger")) == 0


# [claude] MIT-INH-32
def test_mit_inh_32__update_with_a_machineitemupdate_applies_qty_0(db, m1, i1, mk_stock):
    """MIT-INH-32 — update with a MachineItemUpdate applies qty=0.
    Rules: `inherited` R7"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.update(db, db_obj=a, obj_in=MachineItemUpdate(qty=0))

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.qty == 0


# [claude] MIT-INH-33
def test_mit_inh_33__req_qty_and_defective_qty_cannot_be_cleared_through_the_schema(db, m1, i1, mk_stock):
    """MIT-INH-33 — req_qty and defective_qty cannot be cleared through the schema.
    Rules: `inherited` R7"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id, req_qty=7, defective_qty=1)

    result = dao.update(db, db_obj=a, obj_in=MachineItemUpdate(req_qty=None, defective_qty=None))

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.req_qty == 7
    assert row.defective_qty == 1
    assert row.qty == 5


# [claude] MIT-INH-34
def test_mit_inh_34__update_is_flushed_not_committed_a_rollback_restores_the_old_value(db, m1, i1, mk_stock):
    """MIT-INH-34 — update is flushed, not committed: a rollback restores the old value.
    Rules: `inherited` R7, Overview (never commits)"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.update(db, db_obj=a, obj_in={"qty": 9})

        # Then 1
        assert result is a
        # Then 2
        assert count_rows(db, id=a.id, qty=9) == 1
        # Then 3
        sp.rollback()
        row = reread(db, a)
        assert row.qty == 5
        # Then 4
        assert commit_spy.call_count == 0


# [claude] MIT-INH-35
def test_mit_inh_35__update_with_a_dict_clears_req_qty_and_defective_qty(db, m1, i1, mk_stock):
    """MIT-INH-35 — update with a dict clears req_qty and defective_qty.
    Rules: `inherited` R8"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id, req_qty=7, defective_qty=1)

    result = dao.update(db, db_obj=a, obj_in={"req_qty": None, "defective_qty": None})

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.req_qty is None
    assert row.defective_qty is None
    assert row.qty == 5


# [claude] MIT-INH-36
def test_mit_inh_36__update_with_a_dict_moves_the_row_to_a_machine_with_a_free_key(db, m1, m2, i1, mk_stock):
    """MIT-INH-36 — update with a dict moves the row to a machine with a free key.
    Rules: `inherited` R8"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.update(db, db_obj=a, obj_in={"machine_id": m2.id})

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.machine_id == m2.id
    assert row.item_id == i1.id
    assert row.qty == 5


# [claude] MIT-INH-37
def test_mit_inh_37__update_with_qty_none_in_a_dict_fails_on_flush_and_the_row_stays(db, m1, i1, mk_stock):
    """MIT-INH-37 — update with qty=None in a dict fails on flush and the row stays.
    Rules: `inherited` R8, Errors row 1"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    before_a = snap(db, a)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.update(db, db_obj=a, obj_in={"qty": None})
    # Then 2
    assert isinstance(exc.value.orig, NotNullViolation)
    # Then 3
    assert 'column "qty"' in str(exc.value.orig)
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    row = reread(db, a)
    assert row.qty == 5


# [claude] MIT-INH-38
def test_mit_inh_38__remove_hard_deletes_the_row_and_returns_it_nothing_else_goes(db, m1, i1, i2, mk_stock):
    """MIT-INH-38 — remove hard-deletes the row and returns it; nothing else goes.
    Rules: `inherited` R9, Side effects"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    a_id = a.id
    before_b = snap(db, b)
    before_m1 = snap(db, m1)
    before_i1 = snap(db, i1)

    result = dao.remove(db, id=a_id)

    # Then 1
    assert result.id == a_id
    # Then 2
    assert count_rows(db, id=a_id) == 0
    # Then 3
    assert snap(db, b) == before_b
    # Then 4
    assert snap(db, m1) == before_m1
    # Then 5
    assert snap(db, i1) == before_i1
    # Then 6
    assert db.scalar(text("select count(*) from machine_item_ledger")) == 0


# [claude] MIT-INH-39
@pytest.mark.xfail(strict=True, reason="BUG-101: Removing a non-existent id raises instead of returning `None`")
def test_mit_inh_39__remove_of_an_id_with_no_row_returns_none_and_deletes_nothing(db, m1, i1, mk_stock):
    """MIT-INH-39 — remove of an id with no row returns None and deletes nothing.
    Rules: `inherited` R9 [BUG-101]"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    before = written(db)
    before_a = snap(db, a)

    result = dao.remove(db, id=MISSING)

    # Then 1
    assert result is None
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, a) == before_a


# [claude] MIT-INH-40
def test_mit_inh_40__remove_is_flushed_not_committed_a_rollback_brings_the_row_back(db, m1, i1, mk_stock):
    """MIT-INH-40 — remove is flushed, not committed: a rollback brings the row back.
    Rules: `inherited` R9, Overview (never commits)"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    a_id = a.id
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        sp = db.begin_nested()
        result = dao.remove(db, id=a_id)

        # Then 1
        assert result.id == a_id
        # Then 2
        assert count_rows(db, id=a_id) == 0
        # Then 3
        sp.rollback()
        assert count_rows(db, id=a_id) == 1
        # Then 4
        assert commit_spy.call_count == 0


# [claude] MIT-INH-41
def test_mit_inh_41__get_returns_a_row_of_any_workspace(db, w2, m9, i9, mk_stock):
    """MIT-INH-41 — get returns a row of any workspace.
    Rules: `inherited` R10"""
    z = mk_stock(machine_id=m9.id, item_id=i9.id, workspace_id=w2.id)

    result = dao.get(db, z.id)

    # Then 1
    assert result.id == z.id
    # Then 2
    assert result.workspace_id == w2.id


# [claude] MIT-INH-42
def test_mit_inh_42__get_returns_none_for_an_unknown_id(db, m1, i1, mk_stock):
    """MIT-INH-42 — get returns None for an unknown id.
    Rules: `inherited` R10"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get(db, MISSING)

    # Then 1
    assert result is None


# [claude] MIT-INH-43
def test_mit_inh_43__get_multi_is_not_scoped_to_a_workspace(db, w2, m1, m9, i1, i9, mk_stock):
    """MIT-INH-43 — get_multi is not scoped to a workspace.
    Rules: `inherited` R10"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    z = mk_stock(machine_id=m9.id, item_id=i9.id, workspace_id=w2.id)

    result = dao.get_multi(db)

    # Then 1
    assert sorted(ids(result)) == [a.id, z.id]


# [claude] MIT-INH-44
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_inh_44__get_multi_returns_the_rows_in_id_order(db, m1, i1, i2, mk_stock):
    """MIT-INH-44 — get_multi returns the rows in id order.
    Rules: `inherited` R10 [BUG-100]"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i2.id)
    a.qty = 6
    db.flush()

    result = dao.get_multi(db)

    # Then 1
    assert sorted(ids(result)) == [a.id, b.id]
    # Then 2
    assert ids(result) == [a.id, b.id]


# [claude] MIT-INH-45
@pytest.mark.xfail(strict=True, reason="BUG-100: BaseDAO list methods have no sort order")
def test_mit_inh_45__the_get_multi_query_asks_the_database_for_id_order(db, m1, i1, mk_stock):
    """MIT-INH-45 — the get_multi query asks the database for id order.
    Rules: `inherited` R10 [BUG-100]"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    with StatementRecorder(db) as recorder:
        result = dao.get_multi(db)
    [sql] = recorder.selects()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "machine_items.id" in order_part
    # Then 4
    assert "DESC" not in order_part


# [claude] MIT-INH-46
def test_mit_inh_46__a_hard_delete_of_a_machine_with_a_stock_row_is_refused_by_the_database(db, m1, i1, mk_stock):
    """MIT-INH-46 — a hard delete of a machine with a stock row is refused by the database.
    Rules: `inherited` R11"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    before_a = snap(db, a)
    before_m1 = snap(db, m1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.execute(text("delete from machines where id = :i"), {"i": m1.id})
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_items_machine_id_fkey" in str(exc.value.orig)
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert snap(db, m1) == before_m1


# [claude] MIT-INH-47
def test_mit_inh_47__a_hard_delete_of_an_item_with_a_stock_row_is_refused_by_the_database(db, m1, i1, mk_stock):
    """MIT-INH-47 — a hard delete of an item with a stock row is refused by the database.
    Rules: `inherited` R11"""
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    before_a = snap(db, a)
    before_i1 = snap(db, i1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.execute(text("delete from items where id = :i"), {"i": i1.id})
    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_items_item_id_fkey" in str(exc.value.orig)
    # Then 4
    assert snap(db, a) == before_a
    # Then 5
    assert snap(db, i1) == before_i1


# [claude] MIT-INH-48
def test_mit_inh_48__a_hard_delete_of_the_workspace_removes_its_stock_rows(db, m1, i1, mk_stock):
    """MIT-INH-48 — a hard delete of the workspace removes its stock rows.
    Rules: `inherited` R11"""
    w3 = make_workspace(db)
    a = mk_stock(machine_id=m1.id, item_id=i1.id)
    b = mk_stock(machine_id=m1.id, item_id=i1.id, workspace_id=w3.id)
    b_id = b.id
    w3_id = w3.id
    before_a = snap(db, a)
    before_m1 = snap(db, m1)
    before_i1 = snap(db, i1)

    db.execute(text("delete from workspaces where id = :i"), {"i": w3_id})

    # Then 1
    assert count_rows(db, id=b_id) == 0
    # Then 2
    assert snap(db, a) == before_a
    # Then 3
    assert snap(db, m1) == before_m1
    # Then 4
    assert snap(db, i1) == before_i1


# [claude] MIT-INH-49
def test_mit_inh_49__without_a_loaded_item_item_name_and_item_unit_are_none():
    """MIT-INH-49 — without a loaded item, item_name and item_unit are None.
    Rules: `inherited` R12"""
    row = MachineItem(item_id=1)

    result = (row.item_name, row.item_unit)

    # Then 1
    assert result[0] is None
    # Then 2
    assert result[1] is None


# [claude] MIT-INH-50
@pytest.mark.xfail(
    strict=False,
    reason="BUG-100: BaseDAO list methods have no sort order "
    "(non-strict: today's order is the physical row order, which can match by accident)",
)
def test_mit_inh_50__get_multi_id_order_holds_across_workspaces_the_higher_workspace_s_row(db, w2, m1, m9, i1, i9, mk_stock):
    """MIT-INH-50 — get_multi id order holds across workspaces, the higher workspace's row first.
    Rules: `inherited` R10 [BUG-100]"""
    z = mk_stock(machine_id=m9.id, item_id=i9.id, workspace_id=w2.id)
    a = mk_stock(machine_id=m1.id, item_id=i1.id)

    result = dao.get_multi(db)

    # Then 1
    assert sorted(ids(result)) == [z.id, a.id]
    # Then 2
    assert ids(result) == [z.id, a.id]


# [claude] MIT-INH-51
@pytest.mark.xfail(strict=True, reason="BUG-101: Removing a non-existent id raises instead of returning `None`")
def test_mit_inh_51__remove_of_an_id_with_no_row_does_not_commit(db, m1, i1, mk_stock):
    """MIT-INH-51 — remove of an id with no row does not commit.
    Rules: `inherited` R9 [BUG-101], Overview (never commits)"""
    mk_stock(machine_id=m1.id, item_id=i1.id)

    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.remove(db, id=MISSING)

        # Then 1
        assert result is None
        # Then 2
        assert commit_spy.call_count == 0
